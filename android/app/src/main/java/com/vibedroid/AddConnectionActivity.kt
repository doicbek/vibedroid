package com.vibedroid

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.vibedroid.databinding.ActivityAddConnectionBinding

class AddConnectionActivity : AppCompatActivity() {

    private lateinit var binding: ActivityAddConnectionBinding
    private lateinit var store: ConnectionsStore

    // Non-null when editing an existing connection
    private var editingId: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityAddConnectionBinding.inflate(layoutInflater)
        setContentView(binding.root)

        store = ConnectionsStore(this)
        editingId = intent.getStringExtra(EXTRA_CONNECTION_ID)

        setSupportActionBar(binding.toolbar)
        supportActionBar?.setDisplayHomeAsUpEnabled(true)

        if (editingId != null) {
            supportActionBar?.title = "Edit Connection"
            // Pre-fill fields
            store.load().find { it.id == editingId }?.let { conn ->
                binding.nameInput.setText(conn.name)
                binding.hostInput.setText(conn.host)
                binding.portInput.setText(conn.port.toString())
            }
        } else {
            supportActionBar?.title = "New Connection"
            binding.portInput.setText("7681")
        }

        binding.saveButton.setOnClickListener { save() }
    }

    private fun save() {
        val name = binding.nameInput.text?.toString()?.trim() ?: ""
        val host = binding.hostInput.text?.toString()?.trim() ?: ""
        val portStr = binding.portInput.text?.toString()?.trim() ?: ""

        if (name.isEmpty()) { binding.nameLayout.error = "Required"; return }
        else binding.nameLayout.error = null

        if (host.isEmpty()) { binding.hostLayout.error = "Required"; return }
        else binding.hostLayout.error = null

        val port = portStr.toIntOrNull()
        if (port == null || port !in 1..65535) {
            binding.portLayout.error = "Enter a valid port (1–65535)"
            return
        }
        binding.portLayout.error = null

        val id = editingId ?: java.util.UUID.randomUUID().toString()
        val conn = Connection(id = id, name = name, host = host, port = port)

        if (editingId != null) store.update(conn) else store.add(conn)
        finish()
    }

    override fun onSupportNavigateUp(): Boolean {
        onBackPressedDispatcher.onBackPressed()
        return true
    }

    companion object {
        const val EXTRA_CONNECTION_ID = "connection_id"
    }
}
