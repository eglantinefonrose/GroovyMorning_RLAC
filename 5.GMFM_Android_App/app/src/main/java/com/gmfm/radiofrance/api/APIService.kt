package com.gmfm.radiofrance.api

import com.gmfm.radiofrance.model.Chronicle
import com.gmfm.radiofrance.model.UserConfig
import retrofit2.http.*

interface APIService {
    @GET
    suspend fun findTodayFolder(
        @Url url: String
    ): Map<String, String>

    @GET
    suspend fun getUserChronicles(
        @Url url: String
    ): List<Chronicle>

    @POST
    suspend fun addChronicle(
        @Url url: String,
        @Query("nomDeChroniques") title: String,
        @Query("chroniqueRealTimecode") startTime: Int,
        @Query("duration") duration: Int
    )

    @DELETE
    suspend fun removeChronicles(
        @Url url: String
    )

    @POST
    suspend fun setUserBaseTime(
        @Url url: String,
        @Query("baseHour") hour: Int,
        @Query("baseMinute") minute: Int
    )

    @GET
    suspend fun getUserBaseTime(
        @Url url: String
    ): UserConfig
}
