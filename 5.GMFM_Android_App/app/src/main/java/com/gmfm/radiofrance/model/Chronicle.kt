package com.gmfm.radiofrance.model

import com.google.gson.annotations.SerializedName

data class Chronicle(
    @SerializedName("nomDeChronique")
    val title: String?,
    @SerializedName("startTime")
    val startTime: Int?,
    @SerializedName("endTime")
    val endTime: Int?,
    val imageUrl: String? = null
) {
    val duration: Int?
        get() = if (startTime != null && endTime != null) endTime - startTime else null

    fun getFormattedTime(baseHour: Int, baseMinute: Int, offsetSeconds: Int? = null): String {
        val effectiveOffset = offsetSeconds ?: startTime ?: 0
        val baseSeconds = (baseHour * 3600) + (baseMinute * 60)
        val totalSeconds = baseSeconds + effectiveOffset
        
        val hour = (totalSeconds / 3600) % 24
        val minute = (totalSeconds % 3600) / 60
        
        return String.format("%02dh%02d", hour, minute)
    }

    val formattedTime: String
        get() = getFormattedTime(globalBaseHour, globalBaseMinute)

    companion object {
        var globalBaseHour: Int = 7
        var globalBaseMinute: Int = 0

        fun updateGlobalStartTime(hour: Int, minute: Int) {
            globalBaseHour = hour
            globalBaseMinute = minute
        }
    }
}
