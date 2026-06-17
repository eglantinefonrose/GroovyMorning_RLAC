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
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
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

@Composable
fun LiveView(
    chronicles: List<Chronicle>,
    mediaController: MediaController?,
    onNavigateToSchedule: () -> Unit,
    onPlayLiveClick: () -> Unit,
    onChronicleClick: (Chronicle) -> Unit
) {
    var currentTitle by remember { mutableStateOf(mediaController?.currentMediaItem?.mediaMetadata?.title?.toString()) }
    var isPlaying by remember { mutableStateOf(mediaController?.isPlaying ?: false) }

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
                LiveChronicleItem(
                    chronicle = chronicle, 
                    isCurrent = isCurrent,
                    isPlaying = isPlaying && isCurrent,
                    onClick = { onChronicleClick(chronicle) }
                )
            }
        }
    }
}

@Composable
fun LiveChronicleItem(
    chronicle: Chronicle, 
    isCurrent: Boolean,
    isPlaying: Boolean,
    onClick: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .border(
                width = if (isCurrent) 1.dp else 0.dp,
                color = if (isCurrent) FranceInter else Color.Transparent,
                shape = RoundedCornerShape(16.dp)
            )
            .clickable { onClick() },
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (isCurrent) FranceInter.copy(alpha = 0.1f) else Color(0xFF1A1A1A)
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
                    .background(if (isCurrent) FranceInter else Color.Gray),
                contentAlignment = Alignment.Center
            ) {
                if (isCurrent && isPlaying) {
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
                        tint = Color.White
                    )
                }
            }
            Spacer(modifier = Modifier.width(16.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    chronicle.title ?: "Sans titre",
                    fontWeight = if (isCurrent) FontWeight.Bold else FontWeight.Normal,
                    color = Color.White
                )
                val durationText = chronicle.duration?.let {
                    val mins = it / 60
                    val secs = it % 60
                    String.format("%02d:%02d", mins, secs)
                } ?: "--:--"
                Text(
                    durationText,
                    color = Color.Gray,
                    style = MaterialTheme.typography.bodySmall
                )
            }
            if (isCurrent && isPlaying) {
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
            Text(
                "L'émission en cours...",
                style = MaterialTheme.typography.bodyLarge,
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
                modifier = Modifier.fillMaxWidth(), 
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Button(
                    onClick = { /* Contact */ },
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(50),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = Color.Black.copy(alpha = 0.3f), 
                        contentColor = Color.White
                    )
                ) {
                    Text("Contact")
                }
                Button(
                    onClick = onNavigateToSchedule,
                    modifier = Modifier.weight(1f),
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
