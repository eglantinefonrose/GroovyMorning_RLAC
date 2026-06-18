package com.gmfm.radiofrance.viewmodel

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gmfm.radiofrance.api.APIService
import com.gmfm.radiofrance.model.Chronicle
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class MainViewModel @Inject constructor(
    private val apiService: APIService
) : ViewModel() {

    private val _chronicles = MutableStateFlow<List<Chronicle>>(emptyList())
    val chronicles: StateFlow<List<Chronicle>> = _chronicles

    private val _isProgramming = MutableStateFlow(false)
    val isProgramming: StateFlow<Boolean> = _isProgramming

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading

    private val _isSimuMode = MutableStateFlow(false)
    val isSimuMode: StateFlow<Boolean> = _isSimuMode

    private val _serverIp = MutableStateFlow("http://10.0.2.2:8000")
    val serverIp: StateFlow<String> = _serverIp

    private val _folderName = MutableStateFlow<String?>(null)
    val folderName: StateFlow<String?> = _folderName

    val baseUrl: String
        get() {
            return if (_isSimuMode.value) {
                "http://10.0.2.2:8000"
            } else {
                val ip = _serverIp.value
                when {
                    ip.startsWith("http") -> ip.removeSuffix("/")
                    ip.contains(":") -> "http://$ip"
                    else -> "http://$ip:8000"
                }
            }
        }

    fun setSimuMode(enabled: Boolean) {
        _isSimuMode.value = enabled
        fetchData()
    }

    fun setServerIp(ip: String) {
        _serverIp.value = ip
        fetchData()
    }

    fun fetchData() {
        viewModelScope.launch {
            _isLoading.value = true
            try {
                val apiBaseUrl = if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/"
                
                // 1. Fetch Folder Name
                try {
                    val folderUrl = "${apiBaseUrl}api/findTodayFolder"
                    val folderResponse = apiService.findTodayFolder(folderUrl, "testUser")
                    _folderName.value = folderResponse["folderName"]
                    Log.d("GMFM_Data", "Today folder: ${_folderName.value}")
                } catch (e: Exception) {
                    Log.e("GMFM_Data", "Error fetching folder name: ${e.message}")
                }

                // 2. Fetch Chronicles
                val chroniclesUrl = "${apiBaseUrl}api/getUserChronicles"
                Log.d("GMFM_Data", "Fetching chronicles from: $chroniclesUrl")
                
                val response = apiService.getUserChronicles(chroniclesUrl, "testUser")
                _chronicles.value = response
                Log.d("GMFM_Data", "Successfully fetched ${response.size} chronicles")
                
            } catch (e: Exception) {
                Log.e("GMFM_Data", "Error fetching data: ${e.message}", e)
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun moveChronicle(fromIndex: Int, toIndex: Int) {
        val list = _chronicles.value.toMutableList()
        if (fromIndex in list.indices && toIndex in list.indices) {
            val item = list.removeAt(fromIndex)
            list.add(toIndex, item)
            _chronicles.value = list
        }
    }

    fun saveProgramming() {
        viewModelScope.launch {
            _isProgramming.value = true
            try {
                val apiBaseUrl = if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/"
                
                // 1. Remove existing chronicles
                val removeUrl = "${apiBaseUrl}api/removeChronicles"
                apiService.removeChronicles(removeUrl, "testUser")
                
                // 2. Add each chronicle in the new order
                val addUrl = "${apiBaseUrl}api/addChronicle"
                val programsToSave = _chronicles.value
                for (chronicle in programsToSave) {
                    apiService.addChronicle(
                        url = addUrl,
                        userId = "testUser",
                        title = chronicle.title ?: "",
                        startTime = chronicle.startTime ?: 0,
                        duration = chronicle.duration ?: 300
                    )
                }
                
                // 3. Refresh data
                fetchData()
                Log.d("GMFM_Data", "Successfully saved programming")
            } catch (e: Exception) {
                Log.e("GMFM_Data", "Error saving programming: ${e.message}", e)
            } finally {
                _isProgramming.value = false
            }
        }
    }

    fun fetchChronicles() = fetchData()
}
