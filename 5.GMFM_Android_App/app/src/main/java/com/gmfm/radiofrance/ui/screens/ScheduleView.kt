package com.gmfm.radiofrance.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.DragHandle
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material3.*
import androidx.compose.material3.pulltorefresh.PullToRefreshContainer
import androidx.compose.material3.pulltorefresh.rememberPullToRefreshState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.gmfm.radiofrance.model.Chronicle
import com.gmfm.radiofrance.viewmodel.MainViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ScheduleView(
    viewModel: MainViewModel = hiltViewModel(),
    onClose: () -> Unit = {}
) {
    val chronicles by viewModel.chronicles.collectAsState()
    val isProgramming by viewModel.isProgramming.collectAsState()
    val isLoadingData by viewModel.isLoading.collectAsState()
    val baseHour by viewModel.baseHour.collectAsState()
    val baseMinute by viewModel.baseMinute.collectAsState()

    val pullToRefreshState = rememberPullToRefreshState()

    if (pullToRefreshState.isRefreshing) {
        LaunchedEffect(true) {
            viewModel.fetchChronicles()
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
            .background(Color.Black)
            .nestedScroll(pullToRefreshState.nestedScrollConnection)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            // Header
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(onClick = onClose) {
                    Icon(
                        imageVector = Icons.Default.Close,
                        contentDescription = "Fermer",
                        tint = Color.White
                    )
                }
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    "Grille des programmes", 
                    style = MaterialTheme.typography.titleLarge, 
                    fontWeight = FontWeight.Bold, 
                    color = Color.White
                )
            }
            
            Spacer(modifier = Modifier.height(24.dp))
            
            Text(
                "Aujourd'hui",
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.Bold,
                color = Color.White
            )
            
            Spacer(modifier = Modifier.height(24.dp))
            
            if (chronicles.isEmpty()) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("Aucune chronique programmée", color = Color.Gray)
                }
            } else {
                LazyColumn(
                    verticalArrangement = Arrangement.spacedBy(0.dp),
                    modifier = Modifier.weight(1f)
                ) {
                    itemsIndexed(chronicles) { index, chronicle ->
                        val displayTime = chronicle.getFormattedTime(7, 0)
                        
                        TimelineRow(
                            chronicle = chronicle,
                            displayTime = displayTime,
                            onMoveUp = if (index > 0) { { viewModel.moveChronicle(index, index - 1) } } else null,
                            onMoveDown = if (index < chronicles.size - 1) { { viewModel.moveChronicle(index, index + 1) } } else null
                        )
                    }
                }
            }
            Spacer(modifier = Modifier.height(100.dp)) // Space for button
        }

        PullToRefreshContainer(
            state = pullToRefreshState,
            modifier = Modifier.align(Alignment.TopCenter),
            containerColor = Color.Black,
            contentColor = Color.White
        )

        // Programmer Button
        Box(
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .fillMaxWidth()
                .background(
                    Brush.verticalGradient(
                        colors = listOf(Color.Transparent, Color.Black.copy(alpha = 0.8f), Color.Black)
                    )
                )
                .padding(bottom = 32.dp, top = 32.dp, start = 24.dp, end = 24.dp)
        ) {
            Button(
                onClick = { viewModel.saveProgramming() },
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(50),
                enabled = !isProgramming,
                colors = ButtonDefaults.buttonColors(
                    containerColor = Color.White, 
                    contentColor = Color.Black
                ),
                contentPadding = PaddingValues(vertical = 16.dp)
            ) {
                if (isProgramming) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(24.dp),
                        color = Color.Black,
                        strokeWidth = 2.dp
                    )
                    Spacer(modifier = Modifier.width(12.dp))
                    Text("Programmation...", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                } else {
                    Text("Programmer", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                }
            }
        }
    }
}

@Composable
fun TimelineRow(
    chronicle: Chronicle,
    displayTime: String,
    onMoveUp: (() -> Unit)? = null,
    onMoveDown: (() -> Unit)? = null
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.Top
    ) {
        // Time and Vertical Line
        Column(
            modifier = Modifier.width(60.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                text = displayTime, 
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Bold,
                color = Color.White.copy(alpha = 0.6f)
            )
            Spacer(modifier = Modifier.height(8.dp))
            Box(
                modifier = Modifier
                    .width(1.dp)
                    .fillMaxHeight()
                    .background(Color.White.copy(alpha = 0.2f))
            )
        }

        Spacer(modifier = Modifier.width(16.dp))

        // Program Card
        Card(
            modifier = Modifier
                .weight(1f)
                .padding(bottom = 16.dp),
            shape = RoundedCornerShape(24.dp),
            colors = CardDefaults.cardColors(containerColor = Color.White.copy(alpha = 0.05f))
        ) {
            Row(
                modifier = Modifier.padding(12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Thumbnail Placeholder
                Box(
                    modifier = Modifier
                        .size(80.dp)
                        .clip(RoundedCornerShape(12.dp))
                        .background(Color.White.copy(alpha = 0.1f)),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(Icons.Default.Mic, null, tint = Color.White)
                }

                Spacer(modifier = Modifier.width(16.dp))

                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        chronicle.title ?: "Chronique sans titre", 
                        fontWeight = FontWeight.Bold, 
                        color = Color.White,
                        style = MaterialTheme.typography.bodyLarge,
                        maxLines = 2
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

                // Move Controls
                Column {
                    if (onMoveUp != null) {
                        IconButton(onClick = onMoveUp, modifier = Modifier.size(32.dp)) {
                            Icon(Icons.Default.KeyboardArrowUp, null, tint = Color.White.copy(alpha = 0.4f))
                        }
                    }
                    Icon(
                        Icons.Default.DragHandle, 
                        null, 
                        tint = Color.White.copy(alpha = 0.4f),
                        modifier = Modifier.padding(vertical = 4.dp).align(Alignment.CenterHorizontally)
                    )
                    if (onMoveDown != null) {
                        IconButton(onClick = onMoveDown, modifier = Modifier.size(32.dp)) {
                            Icon(Icons.Default.KeyboardArrowDown, null, tint = Color.White.copy(alpha = 0.4f))
                        }
                    }
                }
            }
        }
    }
}
