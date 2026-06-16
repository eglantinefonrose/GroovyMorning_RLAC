package com.gmfm.radiofrance

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.List
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.gmfm.radiofrance.network.APIService
import com.gmfm.radiofrance.playback.AudioPlayerManager
import com.gmfm.radiofrance.ui.screens.HomeScreen
import com.gmfm.radiofrance.ui.screens.PlayerScreen
import com.gmfm.radiofrance.ui.screens.SplashScreen
import com.gmfm.radiofrance.ui.theme.GMFMTheme

class MainActivity : ComponentActivity() {
    private lateinit var audioPlayerManager: AudioPlayerManager
    private lateinit var apiService: APIService

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        apiService = APIService.getInstance(this)
        audioPlayerManager = AudioPlayerManager(this, apiService)
        audioPlayerManager.setup()

        setContent {
            GMFMTheme {
                var showSplash by remember { mutableStateOf(true) }

                if (showSplash) {
                    SplashScreen { showSplash = false }
                } else {
                    MainApp(audioPlayerManager, apiService)
                }
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        audioPlayerManager.release()
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainApp(audioPlayerManager: AudioPlayerManager, apiService: APIService) {
    val navController = rememberNavController()
    val items = listOf(
        Screen.Home,
        Screen.Live,
        Screen.Schedule
    )

    Scaffold(
        bottomBar = {
            NavigationBar(containerColor = Color.Black) {
                val navBackStackEntry by navController.currentBackStackEntryAsState()
                val currentDestination = navBackStackEntry?.destination
                items.forEach { screen ->
                    NavigationBarItem(
                        icon = { Icon(screen.icon, contentDescription = null) },
                        label = { Text(screen.label) },
                        selected = currentDestination?.hierarchy?.any { it.route == screen.route } == true,
                        onClick = {
                            navController.navigate(screen.route) {
                                popUpTo(navController.graph.findStartDestination().id) {
                                    saveState = true
                                }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = Color.White,
                            unselectedIconColor = Color.Gray,
                            selectedTextColor = Color.White,
                            unselectedTextColor = Color.Gray,
                            indicatorColor = Color.Transparent
                        )
                    )
                }
            }
        }
    ) { innerPadding ->
        NavHost(navController, startDestination = Screen.Home.route, Modifier.padding(innerPadding)) {
            composable(Screen.Home.route) { 
                HomeScreen(audioPlayerManager, onShowSettings = { /* Show settings sheet */ }) 
            }
            composable(Screen.Live.route) { 
                PlayerScreen(audioPlayerManager) 
            }
            composable(Screen.Schedule.route) { 
                // Simple placeholder for Schedule
                Text("Schedule Screen", color = Color.White)
            }
        }
    }
}

sealed class Screen(val route: String, val label: String, val icon: androidx.compose.ui.graphics.vector.ImageVector) {
    object Home : Screen("home", "Home", Icons.Default.Home)
    object Live : Screen("live", "Live", Icons.Default.PlayArrow)
    object Schedule : Screen("schedule", "Programmes", Icons.Default.List)
}
