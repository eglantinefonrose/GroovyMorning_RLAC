package com.gmfm.radiofrance.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.gmfm.radiofrance.playback.AudioPlayerManager

@Composable
fun PlayerScreen(audioPlayerManager: AudioPlayerManager) {
    val programs by audioPlayerManager.programs.collectAsState()
    val currentIndex by audioPlayerManager.currentProgramIndex.collectAsState()
    val isPlaying by audioPlayerManager.isPlaying.collectAsState()
    val currentTime by audioPlayerManager.currentTime.collectAsState()
    val duration by audioPlayerManager.duration.collectAsState()
    val isBuffering by audioPlayerManager.isBuffering.collectAsState()

    val currentProgram = programs.getOrNull(currentIndex)

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black)
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        // Thumbnail/Icon placeholder
        Box(
            modifier = Modifier
                .size(260.dp)
                .background(Color.DarkGray, CircleShape),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = Icons.Default.MusicNote,
                contentDescription = null,
                modifier = Modifier.size(100.dp),
                tint = Color.Gray
            )
        }

        Spacer(modifier = Modifier.height(48.dp))

        // Title and Artist
        Text(
            text = currentProgram?.title ?: "No Title",
            color = Color.White,
            fontSize = 24.sp,
            fontWeight = FontWeight.Bold
        )
        Text(
            text = "GMFM Radio",
            color = Color.Gray,
            fontSize = 18.sp
        )

        Spacer(modifier = Modifier.height(48.dp))

        // Progress Bar
        Column(modifier = Modifier.fillMaxWidth()) {
            Slider(
                value = if (duration > 0) currentTime.toFloat() / duration else 0f,
                onValueChange = { audioPlayerManager.seekTo((it * duration).toLong()) },
                colors = SliderDefaults.colors(
                    thumbColor = Color.White,
                    activeTrackColor = Color.White,
                    inactiveTrackColor = Color.DarkGray
                )
            )
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(text = formatTime(currentTime), color = Color.Gray, fontSize = 12.sp)
                Text(text = formatTime(duration), color = Color.Gray, fontSize = 12.sp)
            }
        }

        Spacer(modifier = Modifier.height(48.dp))

        // Controls
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceEvenly,
            verticalAlignment = Alignment.CenterVertically
        ) {
            IconButton(onClick = { audioPlayerManager.previous() }) {
                Icon(Icons.Default.SkipPrevious, contentDescription = null, tint = Color.White, modifier = Modifier.size(48.dp))
            }
            
            Box(contentAlignment = Alignment.Center) {
                if (isBuffering) {
                    CircularProgressIndicator(color = Color.White)
                }
                IconButton(
                    onClick = { audioPlayerManager.togglePlayPause() },
                    modifier = Modifier.size(80.dp)
                ) {
                    Icon(
                        imageVector = if (isPlaying) Icons.Default.PauseCircle else Icons.Default.PlayCircle,
                        contentDescription = null,
                        tint = Color.White,
                        modifier = Modifier.size(80.dp)
                    )
                }
            }

            IconButton(onClick = { audioPlayerManager.next() }) {
                Icon(Icons.Default.SkipNext, contentDescription = null, tint = Color.White, modifier = Modifier.size(48.dp))
            }
        }
    }
}

private fun formatTime(ms: Long): String {
    val totalSeconds = ms / 1000
    val minutes = totalSeconds / 60
    val seconds = totalSeconds % 60
    return String.format("%02d:%02d", minutes, seconds)
}
