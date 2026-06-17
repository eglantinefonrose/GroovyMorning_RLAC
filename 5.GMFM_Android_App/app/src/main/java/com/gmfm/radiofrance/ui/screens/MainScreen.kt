package com.gmfm.radiofrance.ui.screens

import android.content.ComponentName
import android.util.Log
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.scale
import androidx.compose.ui.unit.dp
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.gmfm.radiofrance.ui.navigation.Screen
import androidx.media3.common.MediaItem
import androidx.media3.session.MediaController
import androidx.media3.session.SessionToken
import com.gmfm.radiofrance.audio.PlaybackService
import com.gmfm.radiofrance.model.Chronicle
import com.google.common.util.concurrent.ListenableFuture
import com.google.common.util.concurrent.MoreExecutors

import androidx.hilt.navigation.compose.hiltViewModel
import com.gmfm.radiofrance.viewmodel.MainViewModel
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.filled.*
import com.gmfm.radiofrance.ui.theme.FranceInter
import androidx.media3.common.Player
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight

@Composable
fun MainScreen(viewModel: MainViewModel = hiltViewModel()) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val navController = rememberNavController()
    
    val isSimuMode by viewModel.isSimuMode.collectAsState()
    val serverIp by viewModel.serverIp.collectAsState()
    val chronicles by viewModel.chronicles.collectAsState()
    
    var isPlayerOpen by remember { mutableStateOf(false) }
    var showSettingsDialog by remember { mutableStateOf(false) }

    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route

    BackHandler(enabled = isPlayerOpen) {
        isPlayerOpen = false
    }
    
    var mediaController by remember { mutableStateOf<MediaController?>(null) }

    LaunchedEffect(Unit) {
        viewModel.fetchChronicles()
        
        val sessionToken = SessionToken(context, ComponentName(context, PlaybackService::class.java))
        val future = MediaController.Builder(context, sessionToken).buildAsync()
        future.addListener({
            mediaController = future.get()
            Log.d("GMFM_Audio", "MediaController connected")
        }, MoreExecutors.directExecutor())
    }

    val cleanChronicleName = { name: String ->
        // Normalize to remove accents (e.g., Météo -> Meteo)
        val normalized = java.text.Normalizer.normalize(name, java.text.Normalizer.Form.NFD)
        val accentRemoved = normalized.replace(Regex("\\p{InCombiningDiacriticalMarks}+"), "")
        // Backend Java: name.replaceAll("[^a-zA-Z0-9]", "_")
        accentRemoved.replace(Regex("[^a-zA-Z0-9]"), "_")
    }

    val playChronicle = { chronicle: Chronicle ->
        try {
            val title = chronicle.title
            val folder = viewModel.folderName.value
            
            if (title == null) {
                Log.e("GMFM_Audio", "Impossible de lire la chronique : Titre est NULL")
            } else if (folder == null) {
                Log.e("GMFM_Audio", "Impossible de lire la chronique : Folder est NULL. Tentative de re-fetch...")
                viewModel.fetchData()
            } else {
                mediaController?.let { controller ->
                    // Match Backend Cleaning:
                    val cleanName = cleanChronicleName(title)
                    
                    // iOS logic: addingPercentEncoding(withAllowedCharacters: .urlPathAllowed)
                    // We encode the cleanName but allow characters that iOS urlPathAllowed includes.
                    // Note: slashes in cleanName (if any) would be underscores anyway now.
                    val encodedTitle = android.net.Uri.encode(cleanName, ":@!$&'()*+,;=")
                    
                    val baseUrl = viewModel.baseUrl.removeSuffix("/")
                    
                    // The 'folder' already contains 'userID_testUser/session_...'
                    // We must ensure the slashes in 'folder' are preserved and not encoded.
                    val rawUrl = "$baseUrl/$folder/$encodedTitle/$encodedTitle.m3u8"
                    
                    // Clean URL to prevent double slashes (common source of 404)
                    val url = rawUrl.replace(Regex("(?<!:)/{2,}"), "/")
                    
                    Log.d("GMFM_Audio", "🎵 Audio Playback Call: $url")
                    Log.d("GMFM_Audio", "DEBUG: baseUrl=$baseUrl")
                    Log.d("GMFM_Audio", "DEBUG: folder=$folder")
                    Log.d("GMFM_Audio", "DEBUG: clean=$cleanName")
                    
                    val mediaItem = MediaItem.Builder()
                        .setUri(url)
                        .setMimeType(androidx.media3.common.MimeTypes.APPLICATION_M3U8)
                        .setMediaMetadata(
                            androidx.media3.common.MediaMetadata.Builder()
                                .setTitle(title)
                                .build()
                        )
                        .build()
                    
                    controller.setMediaItem(mediaItem)
                    controller.prepare()
                    controller.play()
                } ?: Log.e("GMFM_Audio", "MediaController not ready!")
            }
        } catch (e: Exception) {
            Log.e("GMFM_Audio", "Crash prevented in playChronicle: ${e.message}", e)
        }
    }

    val playLive = {
        if (chronicles.isNotEmpty()) {
            Log.d("GMFM_Audio", "🎵 API Call (Stream): Starting first chronicle as live")
            playChronicle(chronicles.first())
            isPlayerOpen = true
        } else {
            Log.e("GMFM_Audio", "Aucune chronique disponible pour le direct")
            viewModel.fetchData()
        }
    }

    // Clean up mediaController on dispose
    DisposableEffect(Unit) {
        onDispose {
            mediaController?.release()
        }
    }

    val items = listOf(
        Screen.Home,
        Screen.Music,
        Screen.Live,
        Screen.Search,
        Screen.Library
    )

    LaunchedEffect(currentRoute, mediaController?.currentMediaItem) {
        if (currentRoute == Screen.Live.route && mediaController?.currentMediaItem != null) {
            isPlayerOpen = true
        }
    }

    Scaffold(
        bottomBar = {
            Column {
                // Mini Player
                val showMiniPlayer = currentRoute != Screen.Live.route && 
                                   currentRoute != Screen.Schedule.route && 
                                   !isPlayerOpen && 
                                   mediaController?.currentMediaItem != null
                
                AnimatedVisibility(
                    visible = showMiniPlayer,
                    enter = slideInVertically(initialOffsetY = { it }),
                    exit = slideOutVertically(targetOffsetY = { it })
                ) {
                    MiniPlayer(
                        mediaController = mediaController,
                        onClick = {
                            navController.navigate(Screen.Live.route) {
                                popUpTo(navController.graph.findStartDestination().id) {
                                    saveState = true
                                }
                                launchSingleTop = true
                                restoreState = true
                            }
                        }
                    )
                }

                NavigationBar(
                    containerColor = MaterialTheme.colorScheme.background,
                    contentColor = MaterialTheme.colorScheme.onBackground
                ) {
                    val currentDestination = navBackStackEntry?.destination
                    items.forEach { screen ->
                        NavigationBarItem(
                            icon = { Icon(screen.icon!!, contentDescription = null) },
                            label = { Text(screen.label!!) },
                            selected = currentDestination?.hierarchy?.any { it.route == screen.route } == true,
                            onClick = {
                                isPlayerOpen = false
                                navController.navigate(screen.route) {
                                    popUpTo(navController.graph.findStartDestination().id) {
                                        saveState = true
                                    }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            }
                        )
                    }
                }
            }
        }
    ) { innerPadding ->
        Box(modifier = Modifier
            .padding(innerPadding)
            .fillMaxSize()
        ) {
            NavHost(
                navController, 
                startDestination = Screen.Home.route,
                modifier = Modifier.fillMaxSize()
            ) {
                composable(Screen.Home.route) { 
                    HomeView(
                        viewModel = viewModel,
                        onSettingsClick = { showSettingsDialog = true },
                        onPlayClick = { chronicle ->
                            playChronicle(chronicle)
                            isPlayerOpen = true
                        }
                    ) 
                }
                composable(Screen.Music.route) { MusicView() }
                composable(Screen.Live.route) { 
                    LiveView(
                        onNavigateToSchedule = { navController.navigate(Screen.Schedule.route) },
                        onPlayClick = { 
                            playLive()
                        }
                    ) 
                }
                composable(Screen.Search.route) { SearchView() }
                composable(Screen.Library.route) { LibraryView() }
                composable(Screen.Schedule.route) { 
                    ScheduleView(viewModel = viewModel) 
                }
            }

            // Settings & Simu Overlay
            Box(
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .padding(8.dp)
            ) {
                Column(horizontalAlignment = Alignment.End) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        // Gear Icon Button
                        IconButton(onClick = { showSettingsDialog = true }) {
                            Icon(
                                Icons.Default.Settings, 
                                contentDescription = "Settings", 
                                tint = MaterialTheme.colorScheme.onBackground,
                                modifier = Modifier.size(20.dp)
                            )
                        }
                        
                        Text(
                            "Simu", 
                            color = MaterialTheme.colorScheme.onBackground, 
                            style = MaterialTheme.typography.labelSmall,
                            modifier = Modifier.padding(end = 4.dp)
                        )
                        Switch(
                            checked = isSimuMode,
                            onCheckedChange = { viewModel.setSimuMode(it) },
                            modifier = Modifier.scale(0.7f)
                        )
                    }
                    if (isSimuMode) {
                        Text(
                            serverIp, 
                            color = MaterialTheme.colorScheme.primary, 
                            style = MaterialTheme.typography.labelSmall,
                            modifier = Modifier.padding(end = 12.dp)
                        )
                    }
                }
            }
        }

        // Settings Dialog
        if (showSettingsDialog) {
            var tempIp by remember { mutableStateOf(serverIp) }
            AlertDialog(
                onDismissRequest = { showSettingsDialog = false },
                title = { Text("Réglages Serveur") },
                text = {
                    Column {
                        Text("Adresse IP du serveur :")
                        Spacer(modifier = Modifier.height(8.dp))
                        TextField(
                            value = tempIp,
                            onValueChange = { tempIp = it },
                            placeholder = { Text("ex: 192.168.1.100") },
                            singleLine = true
                        )
                    }
                },
                confirmButton = {
                    Button(onClick = { 
                        viewModel.setServerIp(tempIp)
                        showSettingsDialog = false 
                    }) {
                        Text("OK")
                    }
                },
                dismissButton = {
                    TextButton(onClick = { showSettingsDialog = false }) {
                        Text("Annuler")
                    }
                }
            )
        }

        // Full Screen Player
        AnimatedVisibility(
            visible = isPlayerOpen,
            enter = slideInVertically(initialOffsetY = { it }),
            exit = slideOutVertically(targetOffsetY = { it })
        ) {
            PlayerView(
                mediaController = mediaController,
                chronicles = chronicles,
                onClose = { isPlayerOpen = false }
            )
        }
    }
}

@Composable fun MusicView() { Box(modifier = Modifier.padding(16.dp)) { Text("Musique View Placeholder", color = MaterialTheme.colorScheme.onBackground) } }
@Composable fun SearchView() { Box(modifier = Modifier.padding(16.dp)) { Text("Search View Placeholder", color = MaterialTheme.colorScheme.onBackground) } }
@Composable fun LibraryView() { Box(modifier = Modifier.padding(16.dp)) { Text("Library View Placeholder", color = MaterialTheme.colorScheme.onBackground) } }

@Composable
fun MiniPlayer(
    mediaController: MediaController?,
    onClick: () -> Unit
) {
    var isPlaying by remember { mutableStateOf(mediaController?.isPlaying ?: false) }
    var currentTitle by remember { mutableStateOf(mediaController?.currentMediaItem?.mediaMetadata?.title?.toString() ?: "Aucun titre") }

    DisposableEffect(mediaController) {
        val listener = object : Player.Listener {
            override fun onIsPlayingChanged(playing: Boolean) {
                isPlaying = playing
            }
            override fun onMediaMetadataChanged(metadata: androidx.media3.common.MediaMetadata) {
                currentTitle = metadata.title?.toString() ?: "Inconnu"
            }
        }
        mediaController?.addListener(listener)
        onDispose {
            mediaController?.removeListener(listener)
        }
    }

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 8.dp, vertical = 4.dp),
        contentAlignment = Alignment.Center
    ) {
        Surface(
            modifier = Modifier
                .fillMaxWidth(0.95f)
                .height(64.dp)
                .clickable { onClick() },
            shape = RoundedCornerShape(16.dp),
            color = FranceInter,
            tonalElevation = 8.dp
        ) {
            Row(
                modifier = Modifier
                    .padding(horizontal = 16.dp)
                    .fillMaxSize(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Mini Logo/Icon
                Box(
                    modifier = Modifier
                        .size(40.dp)
                        .clip(RoundedCornerShape(8.dp))
                        .background(androidx.compose.ui.graphics.Color.White.copy(alpha = 0.2f)),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(Icons.Default.Radio, null, tint = androidx.compose.ui.graphics.Color.White)
                }

                Spacer(modifier = Modifier.width(12.dp))

                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = "France Inter",
                        style = MaterialTheme.typography.labelSmall,
                        color = androidx.compose.ui.graphics.Color.White.copy(alpha = 0.7f)
                    )
                    Text(
                        text = currentTitle,
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.Bold,
                        color = androidx.compose.ui.graphics.Color.White,
                        maxLines = 1,
                        overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis
                    )
                }

                IconButton(
                    onClick = { 
                        if (isPlaying) mediaController?.pause() else mediaController?.play()
                    }
                ) {
                    Icon(
                        if (isPlaying) Icons.Default.Pause else Icons.Default.PlayArrow,
                        contentDescription = "Play/Pause",
                        tint = androidx.compose.ui.graphics.Color.White,
                        modifier = Modifier.size(32.dp)
                    )
                }
            }
        }
    }
}
