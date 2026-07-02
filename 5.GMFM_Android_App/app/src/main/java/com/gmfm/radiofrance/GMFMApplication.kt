package com.gmfm.radiofrance

import android.app.Application
import android.util.Log
import dagger.hilt.android.HiltAndroidApp

@HiltAndroidApp
class GMFMApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        Log.e("GMFM_BOOT", "###########################################")
        Log.e("GMFM_BOOT", "L'APPLICATION GMFM EST EN TRAIN DE LANCER !")
        Log.e("GMFM_BOOT", "###########################################")
    }
}
