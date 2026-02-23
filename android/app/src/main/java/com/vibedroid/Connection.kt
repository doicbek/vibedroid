package com.vibedroid

import java.util.UUID

data class Connection(
    val id: String = UUID.randomUUID().toString(),
    val name: String,
    val host: String,
    val port: Int = 7681,
) {
    val url: String get() = "http://$host:$port"
    val wsUrl: String get() = "ws://$host:$port/ws"
}
