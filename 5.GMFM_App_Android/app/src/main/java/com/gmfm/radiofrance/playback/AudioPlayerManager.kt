package com.gmfm.radiofrance.playback

import android.content.Context
import android.net.Uri
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.hls.HlsMediaSource
import androidx.media3.datasource.DefaultDataSource
import com.gmfm.radiofrance.models.Program
import com.gmfm.radiofrance.network.APIService
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.net.URLEncoder

class AudioPlayerManager(private val context: Context, private val apiService: APIService) {
    private val exoPlayer = ExoPlayer.Builder(context).build()
    private val scope = CoroutineScope(Dispatchers.Main + SupervisorJob())

    private val _isPlaying = MutableStateFlow(false)
    val isPlaying: StateFlow<Boolean> = _isPlaying

    private val _isBuffering = MutableStateFlow(false)
    val isBuffering: StateFlow<Boolean> = _isBuffering

    private val _currentTime = MutableStateFlow(0L)
    val currentTime: StateFlow<Long> = _currentTime

    private val _duration = MutableStateFlow(0L)
    val duration: StateFlow<Long> = _duration

    private val _programs = MutableStateFlow<List<Program>>(emptyList())
    val programs: StateFlow<List<Program>> = _programs

    private val _currentProgramIndex = MutableStateFlow(0)
    val currentProgramIndex: StateFlow<Int> = _currentProgramIndex

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading

    private val _errorMessage = MutableStateFlow<String?>(null)
    val errorMessage: StateFlow<String?> = _errorMessage

    private var progressJob: Job? = null

    init {
        exoPlayer.addListener(object : Player.Listener {
            override fun onIsPlayingChanged(isPlaying: Boolean) {
                _isPlaying.value = isPlaying
                if (isPlaying) startProgressUpdate() else stopProgressUpdate()
            }

            override fun onPlaybackStateChanged(state: Int) {
                _isBuffering.value = state == Player.STATE_BUFFERING
                if (state == Player.STATE_READY) {
                    _duration.value = exoPlayer.duration
                }
                if (state == Player.STATE_ENDED) {
                    next()
                }
            }

            override fun onPlayerError(error: androidx.media3.common.PlaybackException) {
                _errorMessage.value = "Playback error: ${error.message}"
                _isLoading.value = false
            }
        })
    }

    fun setup() {
        scope.launch {
            _isLoading.value = true
            try {
                val chronicles = apiService.api.getUserChronicles()
                val baseTime = apiService.api.getUserBaseTime()
                Program.updateGlobalStartTime(baseTime.hour, baseTime.minute)

                val programsList = chronicles.map {
                    Program(
                        title = it.name,
                        time = "--h--",
                        thumbnail = "mic",
                        color = 0xFFE2001A,
                        startTime = it.startTime,
                        duration = it.endTime - it.startTime
                    )
                }
                _programs.value = programsList
                
                if (programsList.isNotEmpty()) {
                    playProgram(0)
                }
            } catch (e: Exception) {
                _errorMessage.value = "Failed to load programs: ${e.message}"
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun playProgram(index: Int) {
        val programsList = _programs.value
        if (index < 0 || index >= programsList.size) return

        _currentProgramIndex.value = index
        val program = programsList[index]
        
        scope.launch {
            _isLoading.value = true
            try {
                val folderName = apiService.api.getTodayFolder().folderName
                val titleEncoded = URLEncoder.encode(program.title.replace(" ", "_"), "UTF-8")
                val url = "${apiService.baseUrl.value}/$folderName/$titleEncoded/$titleEncoded.m3u8"
                
                val mediaItem = MediaItem.fromUri(Uri.parse(url))
                val dataSourceFactory = DefaultDataSource.Factory(context)
                val hlsMediaSource = HlsMediaSource.Factory(dataSourceFactory)
                    .createMediaSource(mediaItem)

                exoPlayer.setMediaSource(hlsMediaSource)
                exoPlayer.prepare()
                exoPlayer.playWhenReady = true
            } catch (e: Exception) {
                _errorMessage.value = "Failed to load audio: ${e.message}"
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun togglePlayPause() {
        if (exoPlayer.isPlaying) exoPlayer.pause() else exoPlayer.play()
    }

    fun next() {
        if (_currentProgramIndex.value < _programs.value.size - 1) {
            playProgram(_currentProgramIndex.value + 1)
        }
    }

    fun previous() {
        if (_currentProgramIndex.value > 0) {
            playProgram(_currentProgramIndex.value - 1)
        }
    }

    fun seekTo(positionMs: Long) {
        exoPlayer.seekTo(positionMs)
    }

    private fun startProgressUpdate() {
        progressJob?.cancel()
        progressJob = scope.launch {
            while (isActive) {
                _currentTime.value = exoPlayer.currentPosition
                delay(500)
            }
        }
    }

    private fun stopProgressUpdate() {
        progressJob?.cancel()
    }

    fun release() {
        exoPlayer.release()
        scope.cancel()
    }
}
