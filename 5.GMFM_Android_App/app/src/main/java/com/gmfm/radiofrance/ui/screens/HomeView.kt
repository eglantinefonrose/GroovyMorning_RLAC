package com.gmfm.radiofrance.ui.screens

import android.util.Log
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.material3.pulltorefresh.PullToRefreshContainer
import androidx.compose.material3.pulltorefresh.rememberPullToRefreshState
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.gmfm.radiofrance.model.Chronicle
import com.gmfm.radiofrance.viewmodel.MainViewModel
import kotlinx.coroutines.delay

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeView(
    viewModel: MainViewModel = hiltViewModel(),
    onSettingsClick: () -> Unit,
    onPlayClick: (Chronicle) -> Unit
) {
    val chronicles by viewModel.chronicles.collectAsState()
    val isLoadingData by viewModel.isLoading.collectAsState()
    
    val pullToRefreshState = rememberPullToRefreshState()
    
    if (pullToRefreshState.isRefreshing) {
        LaunchedEffect(true) {
            viewModel.fetchData()
        }
    }
    
    LaunchedEffect(isLoadingData) {
        if (!isLoadingData) {
            pullToRefreshState.endRefresh()
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
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "Bonjour",
                    style = MaterialTheme.typography.displaySmall,
                    fontWeight = FontWeight.Bold,
                    color = Color.White
                )
            }

            Spacer(modifier = Modifier.height(24.dp))

            if (isLoadingData && chronicles.isEmpty()) {
                SkeletonLoading()
            } else {
                HomeContent(chronicles, onPlayClick)
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
fun SkeletonLoading() {
    Column {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(200.dp)
                .clip(RoundedCornerShape(24.dp))
                .background(Color.DarkGray)
        )
        Spacer(modifier = Modifier.height(16.dp))
        Box(
            modifier = Modifier
                .width(150.dp)
                .height(24.dp)
                .background(Color.DarkGray)
        )
    }
}

@Composable
fun HomeContent(chronicles: List<Chronicle>, onPlayClick: (Chronicle) -> Unit) {
    LazyColumn {
        item {
            Text(
                "À la une", 
                style = MaterialTheme.typography.titleLarge, 
                fontWeight = FontWeight.Bold, 
                color = Color.White
            )
            Spacer(modifier = Modifier.height(16.dp))
            if (chronicles.isEmpty()) {
                Text("Aucune chronique disponible", color = Color.Gray)
            } else {
                LazyRow(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                    items(chronicles) { chronicle ->
                        FeaturedCard(chronicle, onPlayClick)
                    }
                }
            }
        }
    }
}

@Composable
fun FeaturedCard(chronicle: Chronicle, onPlayClick: (Chronicle) -> Unit) {
    Card(
        modifier = Modifier.width(280.dp),
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(containerColor = Color(0xFF1A1A1A))
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(140.dp)
                    .clip(RoundedCornerShape(12.dp))
                    .background(Color.Gray)
            )
            Spacer(modifier = Modifier.height(12.dp))
            Text(chronicle.title ?: "Chronique sans titre", fontWeight = FontWeight.Bold, color = Color.White)
            
            val durationValue = chronicle.duration ?: -1
            if (durationValue >= 0) {
                val mins = durationValue / 60
                val secs = durationValue % 60
                val durationText = String.format("%02d:%02d", mins, secs)
                
                Text(
                    "Chronique • $durationText", 
                    color = Color.Gray, 
                    style = MaterialTheme.typography.bodySmall
                )
            }
            Spacer(modifier = Modifier.height(12.dp))
            Button(
                onClick = { 
                    Log.d("GMFM_UI", "Bouton 'Écouter' cliqué pour: ${chronicle.title}")
                    onPlayClick(chronicle)
                },
                shape = RoundedCornerShape(50),
                colors = ButtonDefaults.buttonColors(
                    containerColor = Color.White, 
                    contentColor = Color.Black
                )
            ) {
                Text("Écouter")
            }
        }
    }
}
