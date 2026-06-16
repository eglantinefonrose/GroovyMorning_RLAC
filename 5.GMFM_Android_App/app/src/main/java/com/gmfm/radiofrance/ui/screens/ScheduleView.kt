package com.gmfm.radiofrance.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.DragHandle
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.gmfm.radiofrance.model.Chronicle
import com.gmfm.radiofrance.viewmodel.MainViewModel

@Composable
fun ScheduleView(viewModel: MainViewModel = hiltViewModel()) {
    val chronicles by viewModel.chronicles.collectAsState()

    Box(modifier = Modifier.fillMaxSize()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                "Grille des Programmes", 
                style = MaterialTheme.typography.headlineMedium, 
                fontWeight = FontWeight.Bold, 
                color = Color.White
            )
            Spacer(modifier = Modifier.height(16.dp))
            
            if (chronicles.isEmpty()) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("Aucune chronique programmée", color = Color.Gray)
                }
            } else {
                LazyColumn(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    items(chronicles) { chronicle ->
                        ChronicleItem(chronicle)
                    }
                }
            }
        }

        Button(
            onClick = { viewModel.fetchData() },
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .padding(bottom = 32.dp, start = 16.dp, end = 16.dp)
                .fillMaxWidth(),
            shape = RoundedCornerShape(50),
            colors = ButtonDefaults.buttonColors(
                containerColor = Color.White, 
                contentColor = Color.Black
            )
        ) {
            Text("Recharger", fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
fun ChronicleItem(chronicle: Chronicle) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = Color(0xFF1A1A1A))
    ) {
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(Icons.Default.DragHandle, contentDescription = "Drag", tint = Color.Gray)
            Spacer(modifier = Modifier.width(16.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(chronicle.title ?: "", fontWeight = FontWeight.Bold, color = Color.White)
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
        }
    }
}
