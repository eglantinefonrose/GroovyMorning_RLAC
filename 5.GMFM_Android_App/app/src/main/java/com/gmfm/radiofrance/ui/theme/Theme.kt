package com.gmfm.radiofrance.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val Black = Color(0xFF000000)
val DarkGray = Color(0xFF1A1A1A)
val Gray = Color(0xFF808080)
val White = Color(0xFFFFFFFF)

val FranceInter = Color(0xFFE2001A)
val FranceInfo = Color(0xFFFFD000)
val FranceCulture = Color(0xFF75338E)
val FranceMusique = Color(0xFFE5007D)

private val DarkColorScheme = darkColorScheme(
    primary = White,
    secondary = Gray,
    background = Black,
    surface = DarkGray,
    onPrimary = Black,
    onSecondary = White,
    onBackground = White,
    onSurface = White
)

@Composable
fun GMFMRadioFranceTheme(
    content: @Composable () -> Unit
) {
    MaterialTheme(
        colorScheme = DarkColorScheme,
        content = content
    )
}
