package com.gmfm.radiofrance.viewmodel

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gmfm.radiofrance.api.APIService
import com.gmfm.radiofrance.data.PreferencesManager
import com.gmfm.radiofrance.model.Chronicle
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class MainViewModel @Inject constructor(
    private val apiService: APIService,
    private val preferencesManager: PreferencesManager
) : ViewModel() {

    init {
        Log.e("GMFM_DEBUG", "------------------------------------------")
        Log.e("GMFM_DEBUG", "🔴 LE VIEWMODEL EST INITIALISÉ")
        Log.e("GMFM_DEBUG", "------------------------------------------")
    }

    private val _isFirstVisit = MutableStateFlow(preferencesManager.isFirstVisit)
    val isFirstVisit: StateFlow<Boolean> = _isFirstVisit

    fun setFirstVisitComplete() {
        preferencesManager.isFirstVisit = false
        _isFirstVisit.value = false
    }

    private val _chronicles = MutableStateFlow<List<Chronicle>>(emptyList())
    val chronicles: StateFlow<List<Chronicle>> = _chronicles

    private val _isProgramming = MutableStateFlow(false)
    val isProgramming: StateFlow<Boolean> = _isProgramming

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading

    private val _showUpdatePopup = MutableStateFlow(false)
    val showUpdatePopup: StateFlow<Boolean> = _showUpdatePopup

    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error

    private val _isSimuMode = MutableStateFlow(false)
    val isSimuMode: StateFlow<Boolean> = _isSimuMode

    private val _serverIp = MutableStateFlow("http://10.0.2.2:8000")
    val serverIp: StateFlow<String> = _serverIp

    private val _folderName = MutableStateFlow<String?>(null)
    val folderName: StateFlow<String?> = _folderName

    private val _baseHour = MutableStateFlow(7)
    val baseHour: StateFlow<Int> = _baseHour

    private val _baseMinute = MutableStateFlow(0)
    val baseMinute: StateFlow<Int> = _baseMinute

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
            Log.i("GMFM_Data", "🚀 Démarrage de fetchData...")
            _isLoading.value = true
            _error.value = null
            try {
                val apiBaseUrl = if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/"
                
                // 1. Fetch Folder Name
                try {
                    val folderUrl = "${apiBaseUrl}api/findTodayFolder"
                    val folderResponse = apiService.findTodayFolder(folderUrl)
                    _folderName.value = folderResponse["folderName"]
                    Log.i("GMFM_Data", "📂 Dossier du jour trouvé: ${_folderName.value}")
                } catch (e: Exception) {
                    Log.e("GMFM_Data", "❌ Erreur dossier: ${e.message}")
                    // Don't fail the whole thing yet, but could be a sign of server down
                }

                // 1b. Fetch User Base Time
                try {
                    val baseTimeUrl = "${apiBaseUrl}api/getUserBaseTime"
                    Log.i("GMFM_Data", "🌐 Appel API Heure: $baseTimeUrl")
                    val baseTimeResponse = apiService.getUserBaseTime(baseTimeUrl)
                    Log.i("GMFM_Data", "📦 Réponse Heure: $baseTimeResponse")
                    
                    val hour = baseTimeResponse.baseHour ?: 7
                    val minute = baseTimeResponse.baseMinute ?: 0
                    _baseHour.value = hour
                    _baseMinute.value = minute
                    Chronicle.updateGlobalStartTime(hour, minute)
                    Log.i("GMFM_Data", "✅ Heure de base appliquée: $hour h $minute")
                } catch (e: Exception) {
                    Log.e("GMFM_Data", "❌ Erreur heure: ${e.message}")
                }

                // 2. Fetch Chronicles
                val chroniclesUrl = "${apiBaseUrl}api/getUserChronicles"
                Log.i("GMFM_Data", "🌐 Appel API Chroniques: $chroniclesUrl")
                
                val response = apiService.getUserChronicles(chroniclesUrl)
                _chronicles.value = response.chronicles.filter { (it.startTime ?: -1) >= 0 }
                Log.i("GMFM_Data", "✅ ${_chronicles.value.size} chroniques filtrées (enregistrables) récupérées")
                
                if (response.updated) {
                    Log.i("GMFM_Data", "⚠️ Grille mise à jour détectée !")
                    _showUpdatePopup.value = true
                }
                
            } catch (e: Exception) {
                Log.e("GMFM_Data", "Error fetching data: ${e.message}", e)
                _error.value = "Erreur de connexion au serveur"
                _chronicles.value = emptyList() // Clear stale data
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun clearError() {
        _error.value = null
    }

    fun dismissUpdatePopup() {
        _showUpdatePopup.value = false
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
                apiService.removeChronicles(removeUrl)
                
                // 2. Add each chronicle in the new order
                val addUrl = "${apiBaseUrl}api/addChronicle"
                val programsToSave = _chronicles.value
                for (chronicle in programsToSave) {
                    apiService.addChronicle(
                        url = addUrl,
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

    fun setUserBaseTime(hour: Int, minute: Int) {
        viewModelScope.launch {
            _isLoading.value = true
            try {
                val apiBaseUrl = if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/"
                val url = "${apiBaseUrl}api/setUserBaseTime"
                apiService.setUserBaseTime(url, hour, minute)
                _baseHour.value = hour
                _baseMinute.value = minute
                Chronicle.updateGlobalStartTime(hour, minute)
                Log.d("GMFM_Data", "Successfully set base time to ${hour}h${minute}")
                // Refresh data to update program times
                fetchData()
            } catch (e: Exception) {
                Log.e("GMFM_Data", "Error setting base time: ${e.message}", e)
            } finally {
                _isLoading.value = false
            }
        }
    }
}
