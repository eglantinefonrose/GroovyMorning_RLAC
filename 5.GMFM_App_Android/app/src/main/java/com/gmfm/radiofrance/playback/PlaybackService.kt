package com.gmfm.radiofrance.playback

import android.content.Intent
import androidx.media3.session.MediaSession
import androidx.media3.session.MediaSessionService
import com.gmfm.radiofrance.network.APIService

class PlaybackService : MediaSessionService() {
    private var mediaSession: MediaSession? = null
    lateinit var audioPlayerManager: AudioPlayerManager

    override fun onCreate() {
        super.onCreate()
        val apiService = APIService.getInstance(this)
        audioPlayerManager = AudioPlayerManager(this, apiService)
        // Note: For a real Media3 implementation, we would wrap ExoPlayer in a MediaSession
        // But for this demo, we'll keep it simple and use AudioPlayerManager directly in UI
    }

    override fun onGetSession(controllerInfo: MediaSession.ControllerInfo): MediaSession? {
        return mediaSession
    }

    override fun onDestroy() {
        mediaSession?.run {
            release()
            mediaSession = null
        }
        audioPlayerManager.release()
        super.onDestroy()
    }
}
