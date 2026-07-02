package com.gmfm.radiofrance.ui.screens

import android.util.Log
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
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
    onChronicleClick: (Chronicle) -> Unit,
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
                if (state == Player.STATE_READY || state == Player.STATE_BUFFERING) {
                    val newDuration = mediaController?.duration ?: 0L
                    if (newDuration > 0) duration = newDuration
                }
            }
            override fun onTimelineChanged(timeline: androidx.media3.common.Timeline, reason: Int) {
                val newDuration = mediaController?.duration ?: 0L
                if (newDuration > 0) duration = newDuration
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

    // Update position and duration periodically
    LaunchedEffect(isPlaying) {
        if (isPlaying) {
            while (true) {
                currentPosition = mediaController?.currentPosition ?: 0L
                // In live streams, duration can increase as segments are added
                val newDuration = mediaController?.duration ?: 0L
                if (newDuration > 0 && newDuration != duration) {
                    duration = newDuration
                }
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
                            Icon(Icons.Filled.Replay10, "", tint = Color.White, modifier = Modifier.size(32.dp)) 
                        }

                        IconButton(onClick = {
                            if (mediaController?.hasPreviousMediaItem() == true) {
                                mediaController.seekToPreviousMediaItem()
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
                            if (mediaController?.hasNextMediaItem() == true) {
                                mediaController.seekToNextMediaItem()
                            }
                        }) {
                            Icon(Icons.Default.SkipNext, "", tint = Color.White, modifier = Modifier.size(32.dp))
                        }

                        IconButton(onClick = { mediaController?.seekForward() }) { 
                            Icon(Icons.Filled.Forward10, "", tint = Color.White, modifier = Modifier.size(32.dp)) 
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Minimize Button
            IconButton(
                onClick = onClose,
                modifier = Modifier
                    .size(44.dp)
                    .background(Color.White.copy(alpha = 0.15f), androidx.compose.foundation.shape.CircleShape)
            ) {
                Icon(
                    imageVector = Icons.Default.Close,
                    contentDescription = "Réduire",
                    tint = Color.White,
                    modifier = Modifier.size(24.dp)
                )
            }

            Spacer(modifier = Modifier.height(16.dp))

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
                    val isCurrent = chronicle.title == currentTitle
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(12.dp))
                            .background(if (isCurrent) FranceInter.copy(alpha = 0.2f) else Color(0xFF1A1A1A))
                            .border(
                                width = if (isCurrent) 1.dp else 0.dp,
                                color = if (isCurrent) FranceInter else Color.Transparent,
                                shape = RoundedCornerShape(12.dp)
                            )
                            .clickable { onChronicleClick(chronicle) }
                            .padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Box(
                            modifier = Modifier
                                .size(40.dp)
                                .clip(RoundedCornerShape(8.dp))
                                .background(if (isCurrent) FranceInter else Color.Gray),
                            contentAlignment = Alignment.Center
                        ) {
                            if (isCurrent && isPlaying) {
                                Icon(Icons.Default.VolumeUp, null, tint = Color.White, modifier = Modifier.size(20.dp))
                            }
                        }
                        Spacer(modifier = Modifier.width(12.dp))
                        Column {
                            Text(
                                chronicle.title ?: "", 
                                color = if (isCurrent) Color.White else Color.White.copy(alpha = 0.9f), 
                                fontWeight = if (isCurrent) FontWeight.Bold else FontWeight.Normal
                            )
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
        }
    }
}

private fun formatTime(ms: Long): String {
    val totalSeconds = ms / 1000
    val minutes = totalSeconds / 60
    val seconds = totalSeconds % 60
    return String.format("%02d:%02d", minutes, seconds)
}
