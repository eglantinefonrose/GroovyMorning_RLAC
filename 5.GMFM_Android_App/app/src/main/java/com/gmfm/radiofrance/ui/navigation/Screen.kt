package com.gmfm.radiofrance.ui.navigation

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.ui.graphics.vector.ImageVector

sealed class Screen(val route: String, val icon: ImageVector? = null, val label: String? = null) {
    object Splash : Screen("splash")
    object Main : Screen("main")
    
    object Home : Screen("home", Icons.Default.Home, "Accueil")
    object Music : Screen("music", Icons.Default.MusicNote, "Musique")
    object Live : Screen("live", Icons.Default.Radio, "Directs")
    object Search : Screen("search", Icons.Default.Search, "Recherche")
    object Library : Screen("library", Icons.Default.Person, "Bibliothèque")
    
    object Schedule : Screen("schedule")
}
