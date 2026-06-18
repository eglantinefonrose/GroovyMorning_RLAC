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

    val formattedTime: String
        get() {
            if (startTime == null) return "--h--"
            val baseSeconds = (globalBaseHour * 3600) + (globalBaseMinute * 60)
            val totalSeconds = baseSeconds + startTime
            
            val hour = (totalSeconds / 3600) % 24
            val minute = (totalSeconds % 3600) / 60
            
            return String.format("%02dh%02d", hour, minute)
        }

    companion object {
        var globalBaseHour: Int = 7
        var globalBaseMinute: Int = 0

        fun updateGlobalStartTime(hour: Int, minute: Int) {
            globalBaseHour = hour
            globalBaseMinute = minute
        }
    }
}
