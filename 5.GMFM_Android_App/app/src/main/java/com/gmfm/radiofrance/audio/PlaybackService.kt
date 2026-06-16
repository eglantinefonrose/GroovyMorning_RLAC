package com.gmfm.radiofrance.audio

import android.content.Intent
import android.util.Log
import androidx.media3.common.Player
import androidx.media3.common.PlaybackException
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.session.MediaSession
import androidx.media3.session.MediaSessionService

class PlaybackService : MediaSessionService() {
    private var mediaSession: MediaSession? = null

    override fun onCreate() {
        super.onCreate()
        val player = ExoPlayer.Builder(this).build()
        player.addListener(object : Player.Listener {
            override fun onPlaybackStateChanged(playbackState: Int) {
                val stateString = when (playbackState) {
                    Player.STATE_IDLE -> "IDLE"
                    Player.STATE_BUFFERING -> "BUFFERING"
                    Player.STATE_READY -> "READY"
                    Player.STATE_ENDED -> "ENDED"
                    else -> "UNKNOWN"
                }
                Log.d("GMFM_Audio", "Playback State changed to: $stateString")
            }

            override fun onPlayerError(error: PlaybackException) {
                val failingUri = player.currentMediaItem?.localConfiguration?.uri
                Log.e("GMFM_Audio", "Player Error: ${error.message}")
                Log.e("GMFM_Audio", "Failing URI: $failingUri")
                Log.e("GMFM_Audio", "Full Error StackTrace:", error)
            }

            override fun onIsPlayingChanged(isPlaying: Boolean) {
                Log.d("GMFM_Audio", "Is Playing: $isPlaying")
            }
        })
        mediaSession = MediaSession.Builder(this, player).build()
        Log.d("GMFM_Audio", "PlaybackService created")
    }

    override fun onGetSession(controllerInfo: MediaSession.ControllerInfo): MediaSession? = mediaSession

    override fun onDestroy() {
        mediaSession?.run {
            player.release()
            release()
            mediaSession = null
        }
        super.onDestroy()
    }
}
