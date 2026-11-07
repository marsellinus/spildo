package com.example.dualaudio

import android.content.Intent
import android.os.Build
import android.service.quicksettings.Tile
import android.service.quicksettings.TileService
import androidx.annotation.RequiresApi

/** Tile panel cepat: ketuk = toggle start/stop tanpa buka aplikasi. */
@RequiresApi(Build.VERSION_CODES.N)
class DualAudioTile : TileService() {

    override fun onStartListening() {
        super.onStartListening()
        qsTile?.state = if (DualAudioService.running) Tile.STATE_ACTIVE else Tile.STATE_INACTIVE
        qsTile?.updateTile()
    }

    override fun onClick() {
        super.onClick()
        if (DualAudioService.running) {
            startService(Intent(this, DualAudioService::class.java).setAction(DualAudioService.ACTION_STOP))
            qsTile?.state = Tile.STATE_INACTIVE
        } else {
            val i = Intent(this, DualAudioService::class.java).putExtra(DualAudioService.EXTRA_MODE, "mirror")
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(i)
            else startService(i)
            qsTile?.state = Tile.STATE_ACTIVE
        }
        qsTile?.updateTile()
    }
}
