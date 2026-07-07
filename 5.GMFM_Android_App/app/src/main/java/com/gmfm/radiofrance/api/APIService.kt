package com.gmfm.radiofrance.api

import com.gmfm.radiofrance.model.Chronicle
import com.gmfm.radiofrance.model.ChroniclesResponse
import com.gmfm.radiofrance.model.UserConfig
import retrofit2.http.*

interface APIService {
    @GET
    suspend fun findTodayFolder(
        @Url url: String,
        @Query("userId") userId: String = "8dcb13c3"
    ): Map<String, String>

    @GET
    suspend fun getUserChronicles(
        @Url url: String,
        @Query("userId") userId: String = "8dcb13c3"
    ): ChroniclesResponse

    @POST
    suspend fun addChronicle(
        @Url url: String,
        @Query("nomDeChroniques") name: String,
        @Query("chroniqueRealTimecode") startTime: Int,
        @Query("duration") duration: Int,
        @Query("userId") userId: String = "8dcb13c3"
    )

    @DELETE
    suspend fun removeChronicles(
        @Url url: String,
        @Query("userId") userId: String = "8dcb13c3"
    )

    @POST
    suspend fun setUserBaseTime(
        @Url url: String,
        @Query("baseHour") hour: Int,
        @Query("baseMinute") minute: Int,
        @Query("userId") userId: String = "8dcb13c3"
    )

    @GET
    suspend fun getUserBaseTime(
        @Url url: String
    ): UserConfig
}
