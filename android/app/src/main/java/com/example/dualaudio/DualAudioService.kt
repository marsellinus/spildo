package com.example.dualaudio

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.media.MediaCodec
import android.media.MediaExtractor
import android.media.MediaFormat
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import kotlin.concurrent.thread
import kotlin.math.sin

/**
 * 2 slot independen: A->internal, B->bluetooth. Lagu beda, jalan bareng.
 * Slot tanpa file = nada uji (A 440Hz, B 880Hz) biar langsung bunyi.
 */
class DualAudioService : Service() {

    companion object {
        const val CH_ID = "dual_audio"
        const val NOTIF_ID = 1
        const val ACTION_STOP = "com.example.dualaudio.STOP"
        const val EXTRA_A = "file_a"
        const val EXTRA_B = "file_b"
        @Volatile var runningA = false
        @Volatile var runningB = false
    }

    private val players = mutableMapOf<String, SlotPlayer>()
    private val workers = mutableMapOf<String, Thread>()
    @Volatile private var stopAll = false

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel(CH_ID, "Dual Audio", NotificationManager.IMPORTANCE_LOW).also {
                getSystemService(NotificationManager::class.java).createNotificationChannel(it)
            }
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopAll()
            stopSelf()
            return START_NOT_STICKY
        }
        stopAll = false
        val (spk, bt) = findInternalBt()
        startForeground(NOTIF_ID, notif())
        startSlot("A", intent?.getStringExtra(EXTRA_A), spk, 440.0) { runningA = it }
        startSlot("B", intent?.getStringExtra(EXTRA_B), bt, 880.0) { runningB = it }
        return START_STICKY
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
        val st = "A:${if (runningA) "jalan" else "stop"} B:${if (runningB) "jalan" else "stop"}"
        return NotificationCompat.Builder(this, CH_ID)
            .setContentTitle("Dual Audio jalan")
            .setContentText(st)
            .setSmallIcon(android.R.drawable.ic_media_play)
            .setContentIntent(open)
            .addAction(android.R.drawable.ic_media_pause, "Stop semua", stop)
            .setOngoing(true)
            .build()
    }

    private fun startSlot(key: String, uri: String?, dev: android.media.AudioDeviceInfo?,
                          testFreq: Double, setFlag: (Boolean) -> Unit) {
        if (workers[key]?.isAlive == true) return
        if (dev == null) return
        val player = SlotPlayer(this)
        if (!player.start(dev)) return
        players[key] = player
        setFlag(true)
        workers[key] = thread(start = true, isDaemon = true) {
            try {
                if (uri != null) playFile(player, uri) else playTone(player, testFreq)
            } catch (_: Exception) {
            } finally {
                player.stop()
                setFlag(false)
            }
        }
    }

    /** Decode MP3/M4A/OGG native via MediaExtractor+MediaCodec ke PCM 44.1k stereo. */
    private fun playFile(player: SlotPlayer, uri: String) {
        val ex = MediaExtractor()
        ex.setDataSource(uri)
        val trackIdx = (0 until ex.trackCount).firstOrNull {
            ex.getTrackFormat(it).getString(MediaFormat.KEY_MIME)?.startsWith("audio/") == true
        } ?: throw IllegalArgumentException("Tak ada trek audio")
        ex.selectTrack(trackIdx)
        val codec = MediaCodec.createDecoderByType(
            ex.getTrackFormat(trackIdx).getString(MediaFormat.KEY_MIME)!!
        )
        codec.configure(ex.getTrackFormat(trackIdx), null, null, 0)
        codec.start()
        val info = MediaCodec.BufferInfo()
        val out = mutableListOf<Short>()
        var eos = false
        while (!stopAll && !eos) {
            val inIdx = codec.dequeueInputBuffer(10_000)
            if (inIdx >= 0) {
                val buf = codec.getInputBuffer(inIdx)!!
                val n = ex.readSampleData(buf, 0)
                if (n < 0) {
                    codec.queueInputBuffer(inIdx, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                    eos = true
                } else {
                    codec.queueInputBuffer(inIdx, 0, n, ex.sampleTime, 0)
                    ex.advance()
                }
            }
            var oi = codec.dequeueOutputBuffer(info, 10_000)
            while (oi >= 0) {
                val buf = codec.getOutputBuffer(oi)!!
                // ponytail: anggap PCM16; ganti bila codec output float (tambah branch PCM_FLOAT)
                val shorts = ShortArray(info.size / 2)
                buf.asShortBuffer().get(shorts)
                // mono -> stereo
                val stereo = if (shorts.size % 2 == 0) shorts else ShortArray(shorts.size * 2) { shorts[it / 2] }
                out.addAll(stereo.toList())
                while (out.size >= 2048) {
                    player.write(out.take(2048).toShortArray())
                    repeat(2048) { out.removeAt(0) }
                }
                codec.releaseOutputBuffer(oi, false)
                if (info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) { eos = true; break }
                oi = codec.dequeueOutputBuffer(info, 0)
            }
        }
        if (out.isNotEmpty() && !stopAll) player.write(out.toShortArray())
        codec.stop(); codec.release(); ex.release()
    }

    private fun playTone(player: SlotPlayer, freq: Double) {
        val buf = ShortArray(1024)
        var phase = 0.0
        while (!stopAll) {
            for (i in buf.indices) {
                buf[i] = (kotlin.math.sin(phase) * 16384).toInt().toShort()
                phase += 2 * Math.PI * freq / 44100
            }
            player.write(buf)
        }
    }

    private fun stopAll() {
        stopAll = true
        workers.values.forEach { try { it.join(800) } catch (_: Exception) {} }
        workers.clear()
        players.values.forEach { it.stop() }
        players.clear()
        runningA = false
        runningB = false
    }

    override fun onDestroy() {
        stopAll()
        super.onDestroy()
    }
}
