package service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import recording.service.Chronicle;

import java.io.BufferedReader;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;

public class PlaylistService {

    private static final Logger logger = LoggerFactory.getLogger(PlaylistService.class);
    private static final String FFMPEG_PATH = "/opt/homebrew/bin/ffmpeg";

    public String generatePlaylist(List<Chronicle> chronicles, String recordingPath, String userId) throws IOException, InterruptedException {
        File recordingDir = new File(recordingPath);
        if (!recordingDir.exists() || !recordingDir.isDirectory()) {
            throw new IOException("Recording path does not exist or is not a directory: " + recordingPath);
        }

        File userDir = new File("media/userID_" + userId);
        File playlistsDir = new File(userDir, "playlists");
        if (!playlistsDir.exists()) {
            playlistsDir.mkdirs();
        }

        // 1. Concatenate all .m4s segments into a single file
        String fullRecordingPath = new File(playlistsDir, "full_recording.aac").getAbsolutePath();
        concatenateSegments(recordingDir, fullRecordingPath);

        // 2. Cut clips for each chronicle
        List<String> clipPaths = new ArrayList<>();
        for (int i = 0; i < chronicles.size(); i++) {
            Chronicle chronicle = chronicles.get(i);
            String clipPath = new File(playlistsDir, "clip_" + i + ".aac").getAbsolutePath();
            cutClip(fullRecordingPath, clipPath, chronicle.getStartTime(), chronicle.getEndTime());
            clipPaths.add(clipPath);
        }

        // 3. Concatenate all clips into the final playlist
        String finalPlaylistPath = new File(playlistsDir, "final_playlist_" + System.currentTimeMillis() + ".mp3").getAbsolutePath();
        concatenateClips(clipPaths, finalPlaylistPath);

        // 4. Cleanup temporary files
        new File(fullRecordingPath).delete();
        for (String clipPath : clipPaths) {
            new File(clipPath).delete();
        }

        return finalPlaylistPath;
    }

    private void concatenateSegments(File recordingDir, String outputPath) throws IOException, InterruptedException {
        List<Path> segmentPaths = Files.walk(recordingDir.toPath())
                .filter(path -> path.toString().endsWith(".m4s"))
                .sorted()
                .collect(Collectors.toList());

        if (segmentPaths.isEmpty()) {
            throw new IOException("No .m4s segments found in " + recordingDir.getAbsolutePath());
        }

        File fileList = File.createTempFile("ffmpeg_list_", ".txt");
        String content = segmentPaths.stream()
                .map(path -> "file '" + path.toAbsolutePath().toString() + "'")
                .collect(Collectors.joining("\n"));
        Files.write(fileList.toPath(), content.getBytes());

        ProcessBuilder processBuilder = new ProcessBuilder(
                FFMPEG_PATH,
                "-f", "concat",
                "-safe", "0",
                "-i", fileList.getAbsolutePath(),
                "-c", "copy",
                outputPath
        );
        executeFfmpegCommand(processBuilder, "Concatenating segments");
        fileList.delete();
    }

    private void cutClip(String inputPath, String outputPath, int startTime, int endTime) throws IOException, InterruptedException {
        int duration = endTime - startTime;
        ProcessBuilder processBuilder = new ProcessBuilder(
                FFMPEG_PATH,
                "-i", inputPath,
                "-ss", String.valueOf(startTime),
                "-t", String.valueOf(duration),
                "-c", "copy",
                outputPath
        );
        executeFfmpegCommand(processBuilder, "Cutting clip for " + outputPath);
    }

    private void concatenateClips(List<String> clipPaths, String outputPath) throws IOException, InterruptedException {
        File fileList = File.createTempFile("ffmpeg_clips_list_", ".txt");
        String content = clipPaths.stream()
                .map(path -> "file '" + path + "'")
                .collect(Collectors.joining("\n"));
        Files.write(fileList.toPath(), content.getBytes());

        ProcessBuilder processBuilder = new ProcessBuilder(
                FFMPEG_PATH,
                "-f", "concat",
                "-safe", "0",
                "-i", fileList.getAbsolutePath(),
                "-c:a", "libmp3lame",
                "-b:a", "192k",
                outputPath
        );
        executeFfmpegCommand(processBuilder, "Concatenating clips");
        fileList.delete();
    }

    private void executeFfmpegCommand(ProcessBuilder processBuilder, String taskName) throws IOException, InterruptedException {
        logger.info("Starting task: {}", taskName);
        logger.info("Executing ffmpeg command: {}", String.join(" ", processBuilder.command()));

        processBuilder.redirectErrorStream(true);
        Process process = processBuilder.start();

        try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
            String line;
            while ((line = reader.readLine()) != null) {
                logger.debug("ffmpeg: {}", line);
            }
        }

        int exitCode = process.waitFor();
        if (exitCode != 0) {
            throw new IOException("ffmpeg command failed with exit code " + exitCode + " for task: " + taskName);
        }
        logger.info("Task '{}' completed successfully.", taskName);
    }
}
