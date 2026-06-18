package com.gmfm.radiofrance.api

import com.gmfm.radiofrance.model.Chronicle
import retrofit2.http.*

interface APIService {
    @GET
    suspend fun findTodayFolder(
        @Url url: String, 
        @Query("userId") userId: String
    ): Map<String, String>

    @GET
    suspend fun getUserChronicles(
        @Url url: String, 
        @Query("userId") userId: String
    ): List<Chronicle>

    @POST
    suspend fun addChronicle(
        @Url url: String,
        @Query("userId") userId: String,
        @Query("nomDeChroniques") title: String,
        @Query("chroniqueRealTimecode") startTime: Int,
        @Query("duration") duration: Int
    )

    @DELETE
    suspend fun removeChronicles(
        @Url url: String, 
        @Query("userId") userId: String
    )

    @POST
    suspend fun setUserBaseTime(
        @Url url: String, 
        @Body baseTime: Map<String, String>
    )

    @GET
    suspend fun getUserBaseTime(
        @Url url: String, 
        @Query("userId") userId: String
    ): Map<String, String>
}
