package tech.layla.client

import okhttp3.Cookie
import okhttp3.CookieJar
import okhttp3.HttpUrl
import org.json.JSONArray
import org.json.JSONObject

interface Store {
    fun get(key: String): String?
    fun put(key: String, value: String?)
}

class MemoryStore : Store {
    private val values = mutableMapOf<String, String>()
    override fun get(key: String) = values[key]
    override fun put(key: String, value: String?) {
        if (value == null) values.remove(key) else values[key] = value
    }
}

/** Та же httpOnly-кука, что у веб-клиента. Нативное приложение хранит её само. */
class SessionJar(private val store: Store = MemoryStore()) : CookieJar {
    private val items = mutableListOf<Cookie>()

    init {
        restore(store.get(KEY))
    }

    override fun saveFromResponse(url: HttpUrl, cookies: List<Cookie>) {
        for (cookie in cookies) {
            items.removeAll { it.name == cookie.name && it.domain == cookie.domain && it.path == cookie.path }
            if (cookie.expiresAt > System.currentTimeMillis()) items.add(cookie)
        }
        store.put(KEY, export())
    }

    override fun loadForRequest(url: HttpUrl): List<Cookie> =
        items.filter { it.matches(url) && it.expiresAt > System.currentTimeMillis() }

    fun sessionToken(): String? = items.firstOrNull { it.name == COOKIE }?.value

    fun clear() {
        items.clear()
        store.put(KEY, null)
    }

    fun export(): String {
        val array = JSONArray()
        items.forEach { cookie ->
            array.put(
                JSONObject()
                    .put("name", cookie.name)
                    .put("value", cookie.value)
                    .put("domain", cookie.domain)
                    .put("path", cookie.path)
                    .put("secure", cookie.secure)
                    .put("httpOnly", cookie.httpOnly)
                    .put("hostOnly", cookie.hostOnly)
                    .put("expires", cookie.expiresAt),
            )
        }
        return array.toString()
    }

    private fun restore(raw: String?) {
        if (raw.isNullOrBlank()) return
        val array = JSONArray(raw)
        for (index in 0 until array.length()) {
            val row = array.getJSONObject(index)
            val builder = Cookie.Builder()
                .name(row.getString("name"))
                .value(row.getString("value"))
                .path(row.optString("path", "/"))
                .expiresAt(row.optLong("expires", Long.MAX_VALUE))
            if (row.optBoolean("hostOnly", true)) builder.hostOnlyDomain(row.getString("domain"))
            else builder.domain(row.getString("domain"))
            if (row.optBoolean("secure")) builder.secure()
            if (row.optBoolean("httpOnly")) builder.httpOnly()
            items.add(builder.build())
        }
    }

    companion object {
        const val COOKIE = "layla_session"
        private const val KEY = "cookies"
    }
}
