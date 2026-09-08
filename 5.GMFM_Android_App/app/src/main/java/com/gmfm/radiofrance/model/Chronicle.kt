package com.gmfm.radiofrance.model

import com.google.gson.annotations.SerializedName

data class Chronicle(
    @SerializedName("title")
    val title: String?,
    @SerializedName("startTime")
    val startTime: Int?,
    @SerializedName("endTime")
    val endTime: Int?,
    val imageUrl: String? = null
) {
    val duration: Int?
        get() = if (startTime != null && endTime != null) endTime - startTime else null

    fun getFormattedTime(offsetSeconds: Int? = null): String {
        val effectiveOffset = offsetSeconds ?: startTime ?: 0
        val baseSeconds = 7 * 3600 // Fixed to 07:00
        val totalSeconds = baseSeconds + effectiveOffset
        
        val hour = (totalSeconds / 3600) % 24
        val minute = (totalSeconds % 3600) / 60
        
        return String.format("%02dh%02d", hour, minute)
    }

    val formattedTime: String
        get() = getFormattedTime()

    companion object {
        fun updateGlobalStartTime(hour: Int, minute: Int) {
            // No longer used, but kept for compatibility if needed or removed
        }
    }
}
