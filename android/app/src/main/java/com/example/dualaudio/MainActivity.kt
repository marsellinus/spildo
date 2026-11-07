package com.example.dualaudio

import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.OpenableColumns
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import com.google.android.material.button.MaterialButton

class MainActivity : AppCompatActivity() {

    private var uriA: Uri? = null
    private var uriB: Uri? = null

    private val pickA = registerForActivityResult(ActivityResultContracts.OpenDocument()) { u: Uri? ->
        if (u != null) {
            contentResolver.takePersistableUriPermission(u, Intent.FLAG_GRANT_READ_URI_PERMISSION)
            uriA = u
            findViewById<TextView>(R.id.fileA).text = "🎵 ${nameOf(u)}"
        }
    }
    private val pickB = registerForActivityResult(ActivityResultContracts.OpenDocument()) { u: Uri? ->
        if (u != null) {
            contentResolver.takePersistableUriPermission(u, Intent.FLAG_GRANT_READ_URI_PERMISSION)
            uriB = u
            findViewById<TextView>(R.id.fileB).text = "🎵 ${nameOf(u)}"
        }
    }

    private fun nameOf(u: Uri): String {
        contentResolver.query(u, null, null, null, null)?.use { c ->
            if (c.moveToFirst()) {
                val i = c.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                if (i >= 0) return c.getString(i)
            }
        }
        return u.lastPathSegment ?: "lagu"
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S &&
            checkSelfPermission(android.Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED
        ) requestPermissions(arrayOf(android.Manifest.permission.BLUETOOTH_CONNECT), 1)
        if (Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) requestPermissions(arrayOf(android.Manifest.permission.POST_NOTIFICATIONS), 2)

        val cardSpeaker = findViewById<TextView>(R.id.cardSpeaker)
        val cardBt = findViewById<TextView>(R.id.cardBt)
        val txtStatus = findViewById<TextView>(R.id.txtStatus)
        val btnToggle = findViewById<MaterialButton>(R.id.btnToggle)

        fun updateDevices() {
            val (spk, bt) = findInternalBt()
            cardSpeaker.text = "🔊 Slot A — Internal: ${spk?.productName ?: "tak ketemu"}"
            cardBt.text = "🎧 Slot B — Bluetooth: ${bt?.productName ?: "belum konek"}"
        }
        updateDevices()
        findViewById<MaterialButton>(R.id.btnRefresh).setOnClickListener { updateDevices() }

        findViewById<MaterialButton>(R.id.btnPickA).setOnClickListener {
            pickA.launch(arrayOf("audio/*"))
        }
        findViewById<MaterialButton>(R.id.btnPickB).setOnClickListener {
            pickB.launch(arrayOf("audio/*"))
        }

        fun syncBtn() {
            val jalan = DualAudioService.runningA || DualAudioService.runningB
            btnToggle.text = if (jalan) "■  STOP SEMUA" else "▶  PUTAR BARENG"
            txtStatus.text = if (jalan)
                "Jalan background. Tanpa file = nada uji (A 440Hz, B 880Hz)."
            else
                "Pilih lagu tiap slot (opsional), lalu PUTAR BARENG."
        }
        syncBtn()

        btnToggle.setOnClickListener {
            if (DualAudioService.runningA || DualAudioService.runningB) {
                startService(Intent(this, DualAudioService::class.java).setAction(DualAudioService.ACTION_STOP))
            } else {
                val i = Intent(this, DualAudioService::class.java)
                    .putExtra(DualAudioService.EXTRA_A, uriA?.toString())
                    .putExtra(DualAudioService.EXTRA_B, uriB?.toString())
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(i)
                else startService(i)
            }
            btnToggle.postDelayed({ syncBtn() }, 400)
        }
    }

    override fun onResume() {
        super.onResume()
        val jalan = DualAudioService.runningA || DualAudioService.runningB
        findViewById<MaterialButton>(R.id.btnToggle).text =
            if (jalan) "■  STOP SEMUA" else "▶  PUTAR BARENG"
    }
}
