package com.example.dualaudio

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioDeviceInfo
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioTrack
import android.os.Build

class AudioSplitter(private val context: Context) {

    enum class Mode { MIRROR, SPLIT }

    private val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    private var trackSpeaker: AudioTrack? = null
    private var trackBt: AudioTrack? = null
    private val sampleRate = 44100
    private var isRunning = false
    var gainSpeaker = 1.0f
        private set
    var gainBt = 1.0f
        private set

    fun setGains(speaker: Float, bt: Float) {
        gainSpeaker = speaker.coerceIn(0f, 1.5f)
        gainBt = bt.coerceIn(0f, 1.5f)
    }

    private fun scaled(src: ShortArray, gain: Float): ShortArray {
        if (gain == 1.0f) return src
        val out = ShortArray(src.size)
        for (i in src.indices) {
            out[i] = (src[i] * gain).toInt().coerceIn(-32768, 32767).toShort()
        }
        return out
    }

    fun findDevices(): Pair<AudioDeviceInfo?, AudioDeviceInfo?> {
        val devices = audioManager.getDevices(AudioManager.GET_DEVICES_OUTPUTS)
        val speaker = devices.firstOrNull { it.type == AudioDeviceInfo.TYPE_BUILTIN_SPEAKER }
        val bt = devices.firstOrNull {
            it.type == AudioDeviceInfo.TYPE_BLUETOOTH_A2DP || it.type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO
        }
        return Pair(speaker, bt)
    }

    fun start(mode: Mode): Boolean {
        if (isRunning) return true
        val (speakerDev, btDev) = findDevices()
        if (speakerDev == null || btDev == null) {
            return false
        }

        val buffSize = AudioTrack.getMinBufferSize(
            sampleRate,
            AudioFormat.CHANNEL_OUT_STEREO,
            AudioFormat.ENCODING_PCM_16BIT
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

        trackSpeaker = AudioTrack.Builder()
            .setAudioAttributes(attr)
            .setAudioFormat(format)
            .setBufferSizeInBytes(buffSize)
            .setTransferMode(AudioTrack.MODE_STREAM)
            .build().apply {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                    preferredDevice = speakerDev
                }
                play()
            }

        trackBt = AudioTrack.Builder()
            .setAudioAttributes(attr)
            .setAudioFormat(format)
            .setBufferSizeInBytes(buffSize)
            .setTransferMode(AudioTrack.MODE_STREAM)
            .build().apply {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                    preferredDevice = btDev
                }
                play()
            }

        isRunning = true
        return true
    }

    fun write(stereoPcm: ShortArray, mode: Mode) {
        if (!isRunning) return

        when (mode) {
            Mode.MIRROR -> {
                trackSpeaker?.write(scaled(stereoPcm, gainSpeaker), 0, stereoPcm.size)
                trackBt?.write(scaled(stereoPcm, gainBt), 0, stereoPcm.size)
            }
            Mode.SPLIT -> {
                // Left channel ke Speaker, Right channel ke BT (stereo format [L, R, L, R...])
                // ponytail: duplikasi sample mono ke stereo channel; ganti bila format audio mono native
                val leftStereo = ShortArray(stereoPcm.size)
                val rightStereo = ShortArray(stereoPcm.size)

                var i = 0
                while (i < stereoPcm.size) {
                    val l = stereoPcm[i]
                    val r = if (i + 1 < stereoPcm.size) stereoPcm[i + 1] else l
                    leftStereo[i] = l
                    leftStereo[i + 1] = l
                    rightStereo[i] = r
                    rightStereo[i + 1] = r
                    i += 2
                }

                trackSpeaker?.write(scaled(leftStereo, gainSpeaker), 0, leftStereo.size)
                trackBt?.write(scaled(rightStereo, gainBt), 0, rightStereo.size)
            }
        }
    }

    fun stop() {
        isRunning = false
        trackSpeaker?.stop()
        trackSpeaker?.release()
        trackSpeaker = null

        trackBt?.stop()
        trackBt?.release()
        trackBt = null
    }
}
