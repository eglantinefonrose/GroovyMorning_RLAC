package com.gmfm.radiofrance.model

import com.google.gson.annotations.SerializedName

data class ChronicleRequest(
    @SerializedName("title")
    val title: String,
    @SerializedName("name")
    val name: String,
    @SerializedName("nom")
    val nom: String,
    @SerializedName("chronique")
    val chronique: String,
    @SerializedName("chronicleName")
    val chronicleName: String,
    @SerializedName("chroniqueRealTimecode")
    val startTime: Int,
    @SerializedName("duration")
    val duration: Int,
    @SerializedName("userId")
    val userId: String = "8dcb13c3"
)
