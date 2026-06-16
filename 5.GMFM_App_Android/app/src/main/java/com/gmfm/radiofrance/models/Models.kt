package com.gmfm.radiofrance.models

import java.util.UUID

data class RadioStation(
    val id: String = UUID.randomUUID().toString(),
    val name: String,
    val color: Long, // Hex color
    val logoName: String,
    val currentShow: String,
    val subtitle: String,
    val hostImage: String
)

data class Program(
    val id: String = UUID.randomUUID().toString(),
    val time: String,
    val title: String,
    val thumbnail: String,
    val color: Long,
    val startTime: Int, // seconds from base
    val duration: Int
) {
    companion object {
        var globalStartHour = 7
        var globalStartMinute = 0

        fun updateGlobalStartTime(hour: Int, minute: Int) {
            globalStartHour = hour
            globalStartMinute = minute
        }
    }

    val formattedTime: String
        get() {
            val baseSeconds = (globalStartHour * 3600) + (globalStartMinute * 60)
            val totalSeconds = baseSeconds + startTime
            val hours = (totalSeconds / 3600) % 24
            val minutes = (totalSeconds % 3600) / 60
            return String.format("%02dh%02d", hours, minutes)
        }
}

data class FeaturedContent(
    val id: String = UUID.randomUUID().toString(),
    val title: String,
    val subtext: String,
    val duration: String,
    val color: Long
)
