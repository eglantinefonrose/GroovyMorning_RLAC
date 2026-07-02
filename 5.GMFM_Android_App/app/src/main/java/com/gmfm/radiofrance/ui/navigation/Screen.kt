package com.gmfm.radiofrance.ui.navigation

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.ui.graphics.vector.ImageVector

sealed class Screen(val route: String, val icon: ImageVector? = null, val label: String? = null) {
    object Splash : Screen("splash")
    object Main : Screen("main")
    
    object Home : Screen("home", Icons.Default.Home, "Accueil")
    object Live : Screen("live", Icons.Default.Radio, "Directs")
    
    object Schedule : Screen("schedule")
}
