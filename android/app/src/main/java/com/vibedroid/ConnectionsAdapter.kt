package com.vibedroid

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.appcompat.widget.PopupMenu
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.vibedroid.databinding.ItemConnectionBinding

class ConnectionsAdapter(
    private val onConnect: (Connection) -> Unit,
    private val onEdit: (Connection) -> Unit,
    private val onDelete: (Connection) -> Unit,
) : ListAdapter<Connection, ConnectionsAdapter.VH>(Differ) {

    inner class VH(private val b: ItemConnectionBinding) : RecyclerView.ViewHolder(b.root) {
        fun bind(conn: Connection) {
            b.nameText.text = conn.name
            b.hostText.text = "${conn.host}:${conn.port}"

            b.root.setOnClickListener { onConnect(conn) }

            b.moreButton.setOnClickListener { v ->
                PopupMenu(v.context, v).apply {
                    inflate(R.menu.connection_menu)
                    setOnMenuItemClickListener { item ->
                        when (item.itemId) {
                            R.id.action_edit   -> { onEdit(conn);   true }
                            R.id.action_delete -> { onDelete(conn); true }
                            else -> false
                        }
                    }
                    show()
                }
            }
        }
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) =
        VH(ItemConnectionBinding.inflate(LayoutInflater.from(parent.context), parent, false))

    override fun onBindViewHolder(holder: VH, position: Int) =
        holder.bind(getItem(position))

    object Differ : DiffUtil.ItemCallback<Connection>() {
        override fun areItemsTheSame(a: Connection, b: Connection) = a.id == b.id
        override fun areContentsTheSame(a: Connection, b: Connection) = a == b
    }
}
