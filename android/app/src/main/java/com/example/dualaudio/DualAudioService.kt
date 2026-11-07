package com.example.dualaudio

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import kotlin.concurrent.thread
import kotlin.math.sin

/** Service ringan: nada uji jalan terus walau Activity ditutup. */
class DualAudioService : Service() {

    companion object {
        const val CH_ID = "dual_audio"
        const val NOTIF_ID = 1
        const val EXTRA_MODE = "mode"
        const val ACTION_STOP = "com.example.dualaudio.STOP"
        @Volatile var running = false
        @Volatile var mirror = true
    }

    private var splitter: AudioSplitter? = null
    private var worker: Thread? = null
    @Volatile private var playing = false

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopPlayback()
            stopSelf()
            return START_NOT_STICKY
        }
        mirror = intent?.getStringExtra(EXTRA_MODE) != "split"
        startPlayback()
        return START_STICKY
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val ch = NotificationChannel(CH_ID, "Dual Audio", NotificationManager.IMPORTANCE_LOW)
            getSystemService(NotificationManager::class.java).createNotificationChannel(ch)
        }
    }

    private fun notif(): Notification {
        val open = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val stop = PendingIntent.getService(
            this, 1, Intent(this, DualAudioService::class.java).setAction(ACTION_STOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        return NotificationCompat.Builder(this, CH_ID)
            .setContentTitle("Dual Audio jalan")
            .setContentText(if (mirror) "Mirror: internal + Bluetooth" else "Split: L→internal, R→BT")
            .setSmallIcon(android.R.drawable.ic_media_play)
            .setContentIntent(open)
            .addAction(android.R.drawable.ic_media_pause, "Stop", stop)
            .setOngoing(true)
            .build()
    }

    private fun startPlayback() {
        if (playing) {
            // update notif bila mode berubah
            startForeground(NOTIF_ID, notif())
            return
        }
        val sp = AudioSplitter(this)
        if (!sp.start(if (mirror) AudioSplitter.Mode.MIRROR else AudioSplitter.Mode.SPLIT)) {
            stopSelf()
            return
        }
        splitter = sp
        playing = true
        running = true
        startForeground(NOTIF_ID, notif())
        worker = thread(start = true, isDaemon = true) {
            val buffer = ShortArray(1024)
            var phaseL = 0.0
            var phaseR = 0.0
            while (playing) {
                var i = 0
                while (i < buffer.size) {
                    buffer[i] = (sin(phaseL) * 16384).toInt().toShort()
                    buffer[i + 1] = (sin(phaseR) * 16384).toInt().toShort()
                    phaseL += 2 * Math.PI * 440.0 / 44100
                    phaseR += 2 * Math.PI * 880.0 / 44100
                    i += 2
                }
                val m = if (mirror) AudioSplitter.Mode.MIRROR else AudioSplitter.Mode.SPLIT
                sp.write(buffer, m)
            }
        }
    }

    private fun stopPlayback() {
        playing = false
        running = false
        try { worker?.join(500) } catch (_: Exception) {}
        worker = null
        splitter?.stop()
        splitter = null
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) stopForeground(STOP_FOREGROUND_REMOVE)
        else @Suppress("DEPRECATION") stopForeground(true)
    }

    override fun onDestroy() {
        stopPlayback()
        super.onDestroy()
    }
}
