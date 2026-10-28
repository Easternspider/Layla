package tech.layla.app

import android.content.Context
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import tech.layla.client.LaylaApi
import tech.layla.client.SessionJar
import tech.layla.client.Store

class PrefStore(context: Context) : Store {
    private val prefs = context.getSharedPreferences("layla", Context.MODE_PRIVATE)
    override fun get(key: String) = prefs.getString(key, null)
    override fun put(key: String, value: String?) {
        prefs.edit().apply { if (value == null) remove(key) else putString(key, value) }.apply()
    }
}

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val store = PrefStore(this)
        val api = LaylaApi(SessionJar(store), store.get("base") ?: "http://10.0.2.2:8080")
        setContent { LaylaApp(api, store) }
    }
}
