package com.gmfm.radiofrance.network

import com.google.gson.annotations.SerializedName
import retrofit2.http.*

data class TodayFolderResponse(
    val status: String,
    val folderName: String
)

data class UserChronicleResponse(
    @SerializedName("nomDeChronique") val name: String,
    val startTime: Int,
    val endTime: Int
)

data class ScheduleResponse(
    val hour: Int,
    val minute: Int
)

interface RadioFranceApi {
    @GET("api/findTodayFolder")
    suspend fun getTodayFolder(@Query("userId") userId: String = "testUser"): TodayFolderResponse

    @GET("api/getUserChronicles")
    suspend fun getUserChronicles(@Query("userId") userId: String = "testUser"): List<UserChronicleResponse>

    @POST("api/setUserBaseTime")
    suspend fun setUserBaseTime(
        @Query("userId") userId: String = "testUser",
        @Query("baseHour") hour: Int,
        @Query("baseMinute") minute: Int
    )

    @GET("api/getUserBaseTime")
    suspend fun getUserBaseTime(@Query("userId") userId: String = "testUser"): ScheduleResponse

    @GET("api/getSchedule")
    suspend fun getSchedule(@Query("userId") userId: String = "testUser"): ScheduleResponse
    
    @GET("api/getPlaylist")
    suspend fun getPlaylist(): List<String>
    
    @POST("api/createPlaylist")
    suspend fun createPlaylist(@Query("chronicles") chronicles: List<String>)
}
