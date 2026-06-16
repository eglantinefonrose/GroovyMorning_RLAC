package com.gmfm.radiofrance.network

import android.content.Context
import android.content.SharedPreferences
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

class APIService(context: Context) {
    private val prefs: SharedPreferences = context.getSharedPreferences("GMFM_Prefs", Context.MODE_PRIVATE)
    
    private val _baseUrl = MutableStateFlow(prefs.getString("customIPAddress", "http://10.155.210.134:8000") ?: "http://10.155.210.134:8000")
    val baseUrl: StateFlow<String> = _baseUrl

    var customIPAddress: String
        get() = _baseUrl.value
        set(value) {
            prefs.edit().putString("customIPAddress", value).apply()
            _baseUrl.value = value
            rebuildApi()
        }

    private var _api: RadioFranceApi = createApi(_baseUrl.value)
    val api: RadioFranceApi get() = _api

    private fun createApi(url: String): RadioFranceApi {
        val logging = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BODY
        }
        val client = OkHttpClient.Builder()
            .addInterceptor(logging)
            .build()

        return Retrofit.Builder()
            .baseUrl(url.ensureTrailingSlash())
            .addConverterFactory(GsonConverterFactory.create())
            .client(client)
            .build()
            .create(RadioFranceApi::class.java)
    }

    private fun rebuildApi() {
        _api = createApi(_baseUrl.value)
    }

    private fun String.ensureTrailingSlash(): String {
        return if (endsWith("/")) this else "$this/"
    }

    companion object {
        @Volatile
        private var INSTANCE: APIService? = null

        fun getInstance(context: Context): APIService {
            return INSTANCE ?: synchronized(this) {
                INSTANCE ?: APIService(context.applicationContext).also { INSTANCE = it }
            }
        }
    }
}
