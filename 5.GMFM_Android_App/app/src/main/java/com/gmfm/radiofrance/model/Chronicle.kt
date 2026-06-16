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
}
