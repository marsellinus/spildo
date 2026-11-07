package com.example.dualaudio

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioDeviceInfo
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioTrack
import android.os.Build

/**
 * Satu player = satu file (PCM stereo) -> satu output device.
 * Dipakai 2x: slot A (internal) + slot B (bluetooth), lagu beda, jalan bareng.
 */
class SlotPlayer(private val context: Context) {

    private val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    private var track: AudioTrack? = null
    private val sampleRate = 44100
    var gain = 1.0f
    var playing = false
        private set

    fun outputs(): List<AudioDeviceInfo> =
        audioManager.getDevices(AudioManager.GET_DEVICES_OUTPUTS).toList()

    fun start(device: AudioDeviceInfo): Boolean {
        if (playing) return true
        val buffSize = AudioTrack.getMinBufferSize(
            sampleRate, AudioFormat.CHANNEL_OUT_STEREO, AudioFormat.ENCODING_PCM_16BIT
        )
        val attr = AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_MEDIA)
            .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
            .build()
        val format = AudioFormat.Builder()
            .setSampleRate(sampleRate)
            .setChannelMask(AudioFormat.CHANNEL_OUT_STEREO)
            .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
            .build()
        return try {
            track = AudioTrack.Builder()
                .setAudioAttributes(attr)
                .setAudioFormat(format)
                .setBufferSizeInBytes(buffSize)
                .setTransferMode(AudioTrack.MODE_STREAM)
                .build().apply {
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) preferredDevice = device
                    play()
                }
            playing = true
            true
        } catch (_: Exception) {
            false
        }
    }

    fun write(stereoPcm: ShortArray) {
        if (!playing) return
        val buf = if (gain == 1.0f) stereoPcm else ShortArray(stereoPcm.size) { i ->
            (stereoPcm[i] * gain).toInt().coerceIn(-32768, 32767).toShort()
        }
        track?.write(buf, 0, buf.size)
    }

    fun stop() {
        playing = false
        try { track?.stop() } catch (_: Exception) {}
        track?.release()
        track = null
    }
}

/** Cari internal + bluetooth. Dipakai UI buat default tiap slot. */
fun Context.findInternalBt(): Pair<AudioDeviceInfo?, AudioDeviceInfo?> {
    val am = getSystemService(Context.AUDIO_SERVICE) as AudioManager
    val devs = am.getDevices(AudioManager.GET_DEVICES_OUTPUTS)
    val spk = devs.firstOrNull { it.type == AudioDeviceInfo.TYPE_BUILTIN_SPEAKER }
    val bt = devs.firstOrNull {
        it.type == AudioDeviceInfo.TYPE_BLUETOOTH_A2DP || it.type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO
    }
    return Pair(spk, bt)
}
