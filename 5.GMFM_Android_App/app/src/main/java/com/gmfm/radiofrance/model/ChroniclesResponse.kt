package com.gmfm.radiofrance.model

import com.google.gson.annotations.SerializedName

data class ChroniclesResponse(
    @SerializedName("updated")
    val updated: Boolean = false,
    @SerializedName("chronicles")
    val chronicles: List<Chronicle> = emptyList()
)
