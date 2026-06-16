package com.gmfm.radiofrance.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.gmfm.radiofrance.models.FeaturedContent
import com.gmfm.radiofrance.playback.AudioPlayerManager

@Composable
fun HomeScreen(audioPlayerManager: AudioPlayerManager, onShowSettings: () -> Unit) {
    val isLoading by audioPlayerManager.isLoading.collectAsState()
    
    val featuredItems = listOf(
        FeaturedContent(
            title = "L'ayatollah Ali Khamenei meurt dans des frappes israélo-américaines...",
            subtext = "L'Esprit public",
            duration = "58 min",
            color = 0xFF1A1A33
        ),
        FeaturedContent(
            title = "L'IA peut-elle sauver le monde ?",
            subtext = "France Culture",
            duration = "45 min",
            color = 0xFF331A4D
        )
    )

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black)
            .verticalScroll(rememberScrollState())
    ) {
        // Header
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp, vertical = 20.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "Bonjour",
                color = Color.White,
                fontSize = 34.sp,
                fontWeight = FontWeight.Bold
            )
            IconButton(onClick = onShowSettings) {
                Icon(
                    imageVector = Icons.Default.Settings,
                    contentDescription = "Settings",
                    tint = Color.White
                )
            }
        }

        // Featured Section
        if (isLoading) {
            FeaturedSkeleton()
        } else {
            FeaturedCarousel(featuredItems)
        }
        
        Spacer(modifier = Modifier.height(100.dp))
    }
}

@Composable
fun FeaturedCarousel(items: List<FeaturedContent>) {
    LazyRow(
        contentPadding = PaddingValues(horizontal = 16.dp),
        horizontalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        items(items) { item ->
            FeaturedCard(item)
        }
    }
}

@Composable
fun FeaturedCard(item: FeaturedContent) {
    Box(
        modifier = Modifier
            .width(320.dp)
            .height(400.dp)
            .background(Color(item.color), RoundedCornerShape(24.dp))
            .padding(24.dp),
        contentAlignment = Alignment.BottomStart
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(
                text = item.title,
                color = Color.White,
                fontSize = 24.sp,
                fontWeight = FontWeight.Bold,
                maxLines = 3
            )
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(text = item.subtext, color = Color.White.copy(alpha = 0.8f), fontSize = 14.sp)
                Text(text = " • ", color = Color.White.copy(alpha = 0.8f))
                Text(text = item.duration, color = Color.White.copy(alpha = 0.8f), fontSize = 14.sp)
            }
            Button(
                onClick = { /* Listen logic */ },
                colors = ButtonDefaults.buttonColors(containerColor = Color.White.copy(alpha = 0.2f)),
                shape = CircleShape,
                contentPadding = PaddingValues(horizontal = 24.dp, vertical = 12.dp)
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.PlayArrow, contentDescription = null, tint = Color.White)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(text = "Écouter", color = Color.White)
                }
            }
        }
    }
}

@Composable
fun FeaturedSkeleton() {
    LazyRow(
        contentPadding = PaddingValues(horizontal = 16.dp),
        horizontalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        items(2) {
            Box(
                modifier = Modifier
                    .width(320.dp)
                    .height(400.dp)
                    .background(Color.White.copy(alpha = 0.1f), RoundedCornerShape(24.dp))
            )
        }
    }
}
