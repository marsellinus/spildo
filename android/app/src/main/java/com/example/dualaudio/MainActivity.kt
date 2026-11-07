package com.example.dualaudio

import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import com.google.android.material.button.MaterialButton
import com.google.android.material.button.MaterialButtonToggleGroup
import com.google.android.material.slider.Slider

class MainActivity : AppCompatActivity() {

    private lateinit var splitter: AudioSplitter
    private var isMirror = true

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            if (checkSelfPermission(android.Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(arrayOf(android.Manifest.permission.BLUETOOTH_CONNECT), 1)
            }
        }
        if (Build.VERSION.SDK_INT >= 33) {
            if (checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(arrayOf(android.Manifest.permission.POST_NOTIFICATIONS), 2)
            }
        }
        splitter = AudioSplitter(this)

        val cardSpeaker = findViewById<TextView>(R.id.cardSpeaker)
        val cardBt = findViewById<TextView>(R.id.cardBt)
        val txtStatus = findViewById<TextView>(R.id.txtStatus)
        val txtModeDesc = findViewById<TextView>(R.id.txtModeDesc)
        val toggleMode = findViewById<MaterialButtonToggleGroup>(R.id.toggleMode)
        val btnMirror = findViewById<MaterialButton>(R.id.btnMirror)
        val btnSplit = findViewById<MaterialButton>(R.id.btnSplit)
        val btnToggle = findViewById<MaterialButton>(R.id.btnToggle)
        val btnRefresh = findViewById<MaterialButton>(R.id.btnRefresh)
        val sliderSpk = findViewById<Slider>(R.id.sliderSpk)
        val sliderBt = findViewById<Slider>(R.id.sliderBt)
        val lblVolSpk = findViewById<TextView>(R.id.lblVolSpk)
        val lblVolBt = findViewById<TextView>(R.id.lblVolBt)

        toggleMode.check(R.id.btnMirror)
        toggleMode.addOnButtonCheckedListener { _, checkedId, isChecked ->
            if (!isChecked) return@addOnButtonCheckedListener
            isMirror = checkedId == R.id.btnMirror
            txtModeDesc.text = if (isMirror)
                "Mirror: kedua output bunyi sama persis."
            else
                "Split: internal = kiri (440Hz), Bluetooth = kanan (880Hz)."
            // Mode jalan ikut berubah tanpa restart suara.
            DualAudioService.mirror = isMirror
            if (DualAudioService.running) restartService()
        }
        btnMirror.setOnClickListener { toggleMode.check(R.id.btnMirror) }
        btnSplit.setOnClickListener { toggleMode.check(R.id.btnSplit) }

        fun updateDevices() {
            val (spk, bt) = splitter.findDevices()
            cardSpeaker.text = "🔊 Internal: ${spk?.productName ?: "tak ketemu"}"
            cardBt.text = "🎧 Bluetooth: ${bt?.productName ?: "belum konek"}"
            cardSpeaker.alpha = if (spk != null) 1f else 0.5f
            cardBt.alpha = if (bt != null) 1f else 0.5f
        }
        updateDevices()
        btnRefresh.setOnClickListener { updateDevices() }

        sliderSpk.addOnChangeListener { _, value, _ ->
            lblVolSpk.text = "🔊 Internal — ${value.toInt()}%"
        }
        sliderBt.addOnChangeListener { _, value, _ ->
            lblVolBt.text = "🎧 Bluetooth — ${value.toInt()}%"
        }

        fun syncBtn() {
            btnToggle.text = if (DualAudioService.running) "■  STOP" else "▶  MULAI"
            txtStatus.text = if (DualAudioService.running)
                "Jalan di background. Tutup aplikasi aman."
            else
                "Siap. Konekkan Bluetooth lalu MULAI."
        }
        syncBtn()

        btnToggle.setOnClickListener {
            if (!DualAudioService.running) {
                if (splitter.findDevices().second == null) {
                    txtStatus.text = "Gagal: Bluetooth belum konek."
                    return@setOnClickListener
                }
                restartService()
            } else {
                startService(Intent(this, DualAudioService::class.java).setAction(DualAudioService.ACTION_STOP))
            }
            // beri jeda kecil biar flag service kebaca
            btnToggle.postDelayed({ syncBtn() }, 300)
        }
    }

    private fun restartService() {
        val i = Intent(this, DualAudioService::class.java)
            .putExtra(DualAudioService.EXTRA_MODE, if (isMirror) "mirror" else "split")
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(i)
        else startService(i)
    }

    override fun onResume() {
        super.onResume()
        findViewById<MaterialButton>(R.id.btnToggle).text =
            if (DualAudioService.running) "■  STOP" else "▶  MULAI"
    }
}
