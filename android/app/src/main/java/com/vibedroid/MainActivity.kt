package com.vibedroid

import android.content.Intent
import android.os.Bundle
import android.view.View
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import com.vibedroid.databinding.ActivityMainBinding

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var store: ConnectionsStore
    private lateinit var adapter: ConnectionsAdapter

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)
        setSupportActionBar(binding.toolbar)

        store = ConnectionsStore(this)

        adapter = ConnectionsAdapter(
            onConnect = { conn ->
                startActivity(
                    Intent(this, TerminalActivity::class.java)
                        .putExtra(TerminalActivity.EXTRA_URL,  conn.url)
                        .putExtra(TerminalActivity.EXTRA_NAME, conn.name)
                )
            },
            onEdit = { conn ->
                startActivity(
                    Intent(this, AddConnectionActivity::class.java)
                        .putExtra(AddConnectionActivity.EXTRA_CONNECTION_ID, conn.id)
                )
            },
            onDelete = { conn ->
                store.delete(conn.id)
                refreshList()
            },
        )

        binding.recyclerView.layoutManager = LinearLayoutManager(this)
        binding.recyclerView.adapter = adapter

        binding.fab.setOnClickListener {
            startActivity(Intent(this, AddConnectionActivity::class.java))
        }

        refreshList()
    }

    override fun onResume() {
        super.onResume()
        refreshList()
    }

    private fun refreshList() {
        val connections = store.load()
        adapter.submitList(connections)
        binding.emptyView.visibility = if (connections.isEmpty()) View.VISIBLE else View.GONE
    }
}
