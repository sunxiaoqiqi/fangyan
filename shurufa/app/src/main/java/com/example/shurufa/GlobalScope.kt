package com.example.shurufa

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob

object GlobalScope {
    private val job = SupervisorJob()
    val scope = CoroutineScope(Dispatchers.Main + job)
}
