package com.gmfm.radiofrance.ui.screens

import android.util.Log
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.gmfm.radiofrance.model.Chronicle
import com.gmfm.radiofrance.ui.theme.FranceInter

import androidx.compose.runtime.*
import androidx.media3.session.MediaController
import androidx.media3.common.Player
import kotlinx.coroutines.delay

@Composable
fun PlayerView(
    mediaController: MediaController?,
    chronicles: List<Chronicle>,
    onClose: () -> Unit
) {
    var isPlaying by remember { mutableStateOf(mediaController?.isPlaying ?: false) }
    var currentTitle by remember { mutableStateOf(mediaController?.currentMediaItem?.mediaMetadata?.title?.toString() ?: "Aucun titre") }
    var currentPosition by remember { mutableStateOf(mediaController?.currentPosition ?: 0L) }
    var duration by remember { mutableStateOf(mediaController?.duration ?: 0L) }

    // Sync state with MediaController
    DisposableEffect(mediaController) {
        val listener = object : Player.Listener {
            override fun onIsPlayingChanged(playing: Boolean) {
                isPlaying = playing
            }
            override fun onMediaMetadataChanged(metadata: androidx.media3.common.MediaMetadata) {
                currentTitle = metadata.title?.toString() ?: "Inconnu"
            }
            override fun onPlaybackStateChanged(state: Int) {
                if (state == Player.STATE_READY) {
                    duration = mediaController?.duration?.coerceAtLeast(0L) ?: 0L
                }
            }
            override fun onPositionDiscontinuity(
                oldPosition: Player.PositionInfo,
                newPosition: Player.PositionInfo,
                reason: Int
            ) {
                currentPosition = newPosition.positionMs
            }
        }
        mediaController?.addListener(listener)
        onDispose {
            mediaController?.removeListener(listener)
        }
    }

    // Update position periodically
    LaunchedEffect(isPlaying) {
        if (isPlaying) {
            while (true) {
                currentPosition = mediaController?.currentPosition ?: 0L
                delay(500)
            }
        }
    }

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = Color.Black
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(20.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // Header Card
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(60.dp),
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(containerColor = Color(0xFF1A1A1A))
            ) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("France Inter", fontWeight = FontWeight.Bold, color = Color.White)
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            // Main Player Card
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(24.dp),
                colors = CardDefaults.cardColors(containerColor = FranceInter)
            ) {
                Column(
                    modifier = Modifier.padding(24.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Box(
                        modifier = Modifier
                            .size(160.dp)
                            .clip(RoundedCornerShape(16.dp))
                            .background(Color.White.copy(alpha = 0.2f)),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = currentTitle.uppercase(), 
                            fontWeight = FontWeight.Bold, 
                            color = Color.White,
                            textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                            modifier = Modifier.padding(8.dp)
                        )
                    }

                    Spacer(modifier = Modifier.height(20.dp))

                    Text(
                        text = currentTitle, 
                        style = MaterialTheme.typography.titleMedium, 
                        color = Color.White,
                        maxLines = 1,
                        overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis
                    )

                    Spacer(modifier = Modifier.height(12.dp))

                    val progress = if (duration > 0) currentPosition.toFloat() / duration.toFloat() else 0f
                    Slider(
                        value = progress,
                        onValueChange = { newProgress ->
                            val seekPos = (newProgress * duration.toFloat()).toLong()
                            mediaController?.seekTo(seekPos)
                        },
                        colors = SliderDefaults.colors(
                            thumbColor = Color.White,
                            activeTrackColor = Color.White,
                            inactiveTrackColor = Color.White.copy(alpha = 0.3f)
                        )
                    )

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(formatTime(currentPosition), color = Color.White.copy(alpha = 0.7f), style = MaterialTheme.typography.labelSmall)
                        Text(formatTime(duration), color = Color.White.copy(alpha = 0.7f), style = MaterialTheme.typography.labelSmall)
                    }

                    Spacer(modifier = Modifier.height(12.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceEvenly,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        IconButton(onClick = { mediaController?.seekBack() }) { 
                            Icon(Icons.Default.Replay, "", tint = Color.White) 
                        }

                        IconButton(onClick = {
                            val currentIndex = chronicles.indexOfFirst { it.title == currentTitle }
                            if (currentIndex > 0) {
                                // This assumes a way to play by chronicle, 
                                // but MediaController only has seekToNext/Previous if items are in a playlist.
                                // For now, we use seekToPrevious which is standard for MediaController.
                                mediaController?.seekToPrevious()
                            }
                        }) {
                            Icon(Icons.Default.SkipPrevious, "", tint = Color.White, modifier = Modifier.size(32.dp))
                        }

                        IconButton(
                            onClick = { 
                                if (isPlaying) mediaController?.pause() else mediaController?.play()
                            }, 
                            modifier = Modifier.size(64.dp)
                        ) { 
                            Icon(
                                if (isPlaying) Icons.Default.PauseCircle else Icons.Default.PlayCircle, 
                                "", 
                                tint = Color.White, 
                                modifier = Modifier.size(64.dp)
                            ) 
                        }

                        IconButton(onClick = {
                            val currentIndex = chronicles.indexOfFirst { it.title == currentTitle }
                            if (currentIndex != -1 && currentIndex < chronicles.size - 1) {
                                mediaController?.seekToNext()
                            }
                        }) {
                            Icon(Icons.Default.SkipNext, "", tint = Color.White, modifier = Modifier.size(32.dp))
                        }

                        IconButton(onClick = { mediaController?.seekForward() }) { 
                            Icon(Icons.Default.Forward, "", tint = Color.White) 
                        }
                    }

                    Spacer(modifier = Modifier.height(16.dp))

                    // Tool Pill
                    Surface(
                        shape = RoundedCornerShape(50),
                        color = Color.Black.copy(alpha = 0.3f)
                    ) {
                        Row(
                            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp), 
                            horizontalArrangement = Arrangement.spacedBy(16.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(Icons.Default.Snooze, "", tint = Color.White)
                            Text("x1", color = Color.White)
                            Icon(Icons.Default.VolumeUp, "", tint = Color.White)
                            Icon(Icons.Default.List, "", tint = Color.White)
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(24.dp))

            // Chronicles List
            Text(
                "Chroniques du jour", 
                color = Color.White, 
                fontWeight = FontWeight.Bold,
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.fillMaxWidth()
            )
            
            Spacer(modifier = Modifier.height(12.dp))

            LazyColumn(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(chronicles) { chronicle ->
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(12.dp))
                            .background(Color(0xFF1A1A1A))
                            .padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Box(
                            modifier = Modifier
                                .size(40.dp)
                                .clip(RoundedCornerShape(8.dp))
                                .background(Color.Gray)
                        )
                        Spacer(modifier = Modifier.width(12.dp))
                        Column {
                            Text(chronicle.title ?: "", color = Color.White, fontWeight = FontWeight.Bold)
                            val durationText = chronicle.duration?.let { 
                                val mins = it / 60
                                val secs = it % 60
                                String.format("%02d:%02d", mins, secs)
                            } ?: "--:--"
                            Text(durationText, color = Color.Gray, style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            IconButton(onClick = onClose) {
                Icon(
                    Icons.Default.Close, 
                    "Close", 
                    tint = Color.White, 
                    modifier = Modifier.size(32.dp)
                )
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
