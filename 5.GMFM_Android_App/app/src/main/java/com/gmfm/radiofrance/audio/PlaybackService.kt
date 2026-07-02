package com.gmfm.radiofrance.audio

import android.content.Intent
import android.util.Log
import androidx.media3.common.Player
import androidx.media3.common.PlaybackException
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.session.MediaSession
import androidx.media3.session.MediaSession.MediaItemsWithStartPosition
import androidx.media3.session.MediaSessionService
import com.google.common.util.concurrent.Futures
import com.google.common.util.concurrent.ListenableFuture

class PlaybackService : MediaSessionService() {
    private var mediaSession: MediaSession? = null

    private val callback = object : MediaSession.Callback {
        override fun onPlaybackResumption(
            mediaSession: MediaSession,
            controller: MediaSession.ControllerInfo
        ): ListenableFuture<MediaItemsWithStartPosition> {
            Log.d("GMFM_Audio", "onPlaybackResumption called")
            // Return an empty list or the current player items if available
            // In this case, we just satisfy the requirement to avoid the crash
            return Futures.immediateFuture(
                MediaItemsWithStartPosition(emptyList(), 0, 0L)
            )
        }
    }

    override fun onCreate() {
        super.onCreate()
        
        val audioAttributes = androidx.media3.common.AudioAttributes.Builder()
            .setUsage(androidx.media3.common.C.USAGE_MEDIA)
            .setContentType(androidx.media3.common.C.CONTENT_TYPE_MUSIC)
            .build()

        val player = ExoPlayer.Builder(this)
            .setAudioAttributes(audioAttributes, true) // true = handle audio focus automatically
            .setHandleAudioBecomingNoisy(true) // pause when headphones unplugged
            .setSeekBackIncrementMs(10000)
            .setSeekForwardIncrementMs(10000)
            .build()
            
        player.addListener(object : Player.Listener {
            private var lastMediaItem: MediaItem? = null
            private var hasSoughtToStartForCurrentItem = false

            override fun onPlaybackStateChanged(playbackState: Int) {
                val stateString = when (playbackState) {
                    Player.STATE_IDLE -> "IDLE"
                    Player.STATE_BUFFERING -> "BUFFERING"
                    Player.STATE_READY -> "READY"
                    Player.STATE_ENDED -> "ENDED"
                    else -> "UNKNOWN"
                }
                Log.d("GMFM_Audio", "Playback State changed to: $stateString")

                if (playbackState == Player.STATE_READY) {
                    checkAndSeekToStart()
                }
            }

            override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) {
                Log.d("GMFM_Audio", "🎵 Media Item Transition: ${mediaItem?.mediaMetadata?.title} (Reason: $reason)")
                hasSoughtToStartForCurrentItem = false
                checkAndSeekToStart()
            }

            override fun onIsPlayingChanged(isPlaying: Boolean) {
                Log.d("GMFM_Audio", "Is Playing: $isPlaying")
                if (isPlaying) {
                    checkAndSeekToStart()
                }
            }

            private fun checkAndSeekToStart() {
                val currentItem = player.currentMediaItem
                if (currentItem != null) {
                    // Reset flag if the media item has changed
                    if (currentItem != lastMediaItem) {
                        lastMediaItem = currentItem
                        hasSoughtToStartForCurrentItem = false
                    }

                    // Only seek if we haven't for this item yet AND the player is ready
                    if (!hasSoughtToStartForCurrentItem && player.playbackState == Player.STATE_READY) {
                        hasSoughtToStartForCurrentItem = true
                        Log.d("GMFM_Audio", "🚀 Forcing INITIAL seek to 0L for track: ${currentItem.mediaMetadata.title}")
                        player.seekTo(0L)
                    }
                }
            }

            override fun onPlayerError(error: PlaybackException) {
                val failingUri = player.currentMediaItem?.localConfiguration?.uri
                Log.e("GMFM_Audio", "Player Error: ${error.message}")
                Log.e("GMFM_Audio", "Failing URI: $failingUri")
                Log.e("GMFM_Audio", "Full Error StackTrace:", error)
            }
        })
        mediaSession = MediaSession.Builder(this, player)
            .setCallback(callback)
            .build()
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
