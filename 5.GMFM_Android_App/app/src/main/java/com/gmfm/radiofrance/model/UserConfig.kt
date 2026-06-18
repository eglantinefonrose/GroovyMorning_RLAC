package com.gmfm.radiofrance.model

import com.google.gson.annotations.SerializedName

data class UserConfig(
    @SerializedName("userId")
    val userId: String?,
    @SerializedName("baseHour")
    val baseHour: Int?,
    @SerializedName("baseMinute")
    val baseMinute: Int?
)
