package com.gmfm.radiofrance.ui.screens

import android.util.Log
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.material3.pulltorefresh.PullToRefreshContainer
import androidx.compose.material3.pulltorefresh.rememberPullToRefreshState
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.clickable
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import com.gmfm.radiofrance.model.Chronicle
import com.gmfm.radiofrance.ui.theme.FranceInter

import androidx.compose.runtime.*
import androidx.media3.session.MediaController
import androidx.media3.common.Player

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LiveView(
    chronicles: List<Chronicle>,
    isLoading: Boolean,
    isAudioAvailable: Boolean,
    onRefresh: () -> Unit,
    mediaController: MediaController?,
    onNavigateToSchedule: () -> Unit,
    onPlayLiveClick: () -> Unit,
    onChronicleClick: (Chronicle) -> Unit
) {
    var currentTitle by remember { mutableStateOf(mediaController?.currentMediaItem?.mediaMetadata?.title?.toString()) }
    var isPlaying by remember { mutableStateOf(mediaController?.isPlaying ?: false) }

    val pullToRefreshState = rememberPullToRefreshState()

    if (pullToRefreshState.isRefreshing) {
        LaunchedEffect(true) {
            onRefresh()
        }
    }

    LaunchedEffect(isLoading) {
        if (!isLoading) {
            pullToRefreshState.endRefresh()
        }
    }

    DisposableEffect(mediaController) {
        val listener = object : Player.Listener {
            override fun onMediaMetadataChanged(metadata: androidx.media3.common.MediaMetadata) {
                currentTitle = metadata.title?.toString()
            }
            override fun onIsPlayingChanged(playing: Boolean) {
                isPlaying = playing
            }
        }
        mediaController?.addListener(listener)
        onDispose {
            mediaController?.removeListener(listener)
        }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .nestedScroll(pullToRefreshState.nestedScrollConnection)
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(16.dp)
        ) {
            Text(
                text = "Directs",
                style = MaterialTheme.typography.displaySmall,
                fontWeight = FontWeight.Bold,
                color = Color.White
            )

            Spacer(modifier = Modifier.height(24.dp))

            LazyColumn(
                verticalArrangement = Arrangement.spacedBy(16.dp),
                modifier = Modifier.fillMaxSize()
            ) {
                item {
                    FranceInterCard(onNavigateToSchedule, onPlayLiveClick)
                }

                item {
                    Text(
                        "Chroniques",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold,
                        color = Color.White,
                        modifier = Modifier.padding(vertical = 8.dp)
                    )
                }

                items(chronicles) { chronicle ->
                    val isCurrent = chronicle.title == currentTitle
                    val itemHasAudio = isAudioAvailable && chronicle.title != null && (chronicle.duration ?: -1) >= 0 && chronicle.endTime != null
                    LiveChronicleItem(
                        chronicle = chronicle, 
                        isCurrent = isCurrent,
                        isAudioAvailable = itemHasAudio,
                        isPlaying = isPlaying && isCurrent,
                        onClick = { onChronicleClick(chronicle) }
                    )
                }
            }
        }

        PullToRefreshContainer(
            state = pullToRefreshState,
            modifier = Modifier.align(Alignment.TopCenter),
            containerColor = Color.Black,
            contentColor = Color.White
        )
    }
}

@Composable
fun LiveChronicleItem(
    chronicle: Chronicle, 
    isCurrent: Boolean,
    isAudioAvailable: Boolean,
    isPlaying: Boolean,
    onClick: () -> Unit
) {
    val contentColor = if (isAudioAvailable) Color.White else Color.Gray
    val iconBackground = if (!isAudioAvailable) Color.DarkGray else if (isCurrent) FranceInter else Color.Gray

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .border(
                width = if (isCurrent && isAudioAvailable) 1.dp else 0.dp,
                color = if (isCurrent) FranceInter else Color.Transparent,
                shape = RoundedCornerShape(16.dp)
            )
            .clickable { onClick() },
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (isCurrent && isAudioAvailable) FranceInter.copy(alpha = 0.1f) else Color(0xFF1A1A1A)
        )
    ) {
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(48.dp)
                    .clip(RoundedCornerShape(8.dp))
                    .background(iconBackground),
                contentAlignment = Alignment.Center
            ) {
                if (isCurrent && isPlaying && isAudioAvailable) {
                    Icon(
                        Icons.Default.VolumeUp, 
                        null, 
                        tint = Color.White, 
                        modifier = Modifier.size(24.dp)
                    )
                } else {
                    Icon(
                        Icons.Default.PlayArrow,
                        null,
                        tint = if (isAudioAvailable) Color.White else Color.Gray
                    )
                }
            }
            Spacer(modifier = Modifier.width(16.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    chronicle.title ?: "Chronique sans titre",
                    fontWeight = if (isCurrent && isAudioAvailable) FontWeight.Bold else FontWeight.Normal,
                    color = contentColor
                )
                val durationValue = chronicle.duration ?: -1
                if (durationValue >= 0) {
                    val mins = durationValue / 60
                    val secs = durationValue % 60
                    val durationText = String.format("%02d:%02d", mins, secs)
                    Text(
                        durationText,
                        color = Color.Gray,
                        style = MaterialTheme.typography.bodySmall
                    )
                }
            }
            if (isCurrent && isPlaying && isAudioAvailable) {
                Text(
                    "EN LECTURE",
                    color = FranceInter,
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold
                )
            }
        }
    }
}

@Composable
fun FranceInterCard(
    onNavigateToSchedule: () -> Unit,
    onPlayLiveClick: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(containerColor = FranceInter)
    ) {
        Column(modifier = Modifier.padding(20.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(), 
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Box(
                    modifier = Modifier
                        .size(60.dp)
                        .clip(CircleShape)
                        .border(2.dp, Color.White.copy(alpha = 0.5f), CircleShape)
                        .background(Color.Gray)
                )
                Icon(
                    Icons.Default.Radio,
                    contentDescription = "Logo",
                    tint = Color.White,
                    modifier = Modifier.size(32.dp)
                )
            }

            Spacer(modifier = Modifier.height(16.dp))

            Text(
                "France Inter",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                color = Color.White
            )

            Spacer(modifier = Modifier.height(24.dp))

            Button(
                onClick = {
                    Log.d("GMFM_UI", "Bouton 'Écouter' cliqué sur l'écran Direct (France Inter)")
                    onPlayLiveClick()
                },
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(50),
                colors = ButtonDefaults.buttonColors(
                    containerColor = Color.White, 
                    contentColor = Color.Black
                )
            ) {
                Text("Écouter", fontWeight = FontWeight.Bold)
            }

            Spacer(modifier = Modifier.height(12.dp))

            Row(
                modifier = Modifier.fillMaxWidth()
            ) {
                Button(
                    onClick = onNavigateToSchedule,
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(50),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = Color.Black.copy(alpha = 0.3f), 
                        contentColor = Color.White
                    )
                ) {
                    Text("Grille")
                }
            }
        }
    }
}
