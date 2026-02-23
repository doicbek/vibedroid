package com.vibedroid

import android.content.Context
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken

class ConnectionsStore(context: Context) {

    private val prefs = context.getSharedPreferences("vibedroid_connections", Context.MODE_PRIVATE)
    private val gson = Gson()
    private val listType = object : TypeToken<List<Connection>>() {}.type

    fun load(): List<Connection> {
        val json = prefs.getString(KEY, null) ?: return emptyList()
        return try {
            gson.fromJson(json, listType) ?: emptyList()
        } catch (e: Exception) {
            emptyList()
        }
    }

    fun save(connections: List<Connection>) {
        prefs.edit().putString(KEY, gson.toJson(connections)).apply()
    }

    fun add(connection: Connection) {
        save(load() + connection)
    }

    fun update(connection: Connection) {
        save(load().map { if (it.id == connection.id) connection else it })
    }

    fun delete(id: String) {
        save(load().filter { it.id != id })
    }

    companion object {
        private const val KEY = "connections_json"
    }
}
