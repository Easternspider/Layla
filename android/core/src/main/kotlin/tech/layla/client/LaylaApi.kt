package tech.layla.client

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class LaylaException(val status: Int, message: String) : RuntimeException(message)

class ApiBody(val text: String) {
    fun items(arrayKey: String? = null): List<JSONObject> {
        val trimmed = text.trim()
        if (trimmed.startsWith("[")) return array(JSONArray(trimmed))
        if (!trimmed.startsWith("{")) return emptyList()
        val obj = JSONObject(trimmed)
        if (arrayKey != null && obj.opt(arrayKey) is JSONArray) return array(obj.getJSONArray(arrayKey))
        return listOf(obj)
    }

    fun obj(): JSONObject = if (text.isBlank()) JSONObject() else JSONObject(text)

    private fun array(value: JSONArray) = (0 until value.length()).map { index ->
        val row = value.get(index)
        if (row is JSONObject) row else JSONObject().put("value", row)
    }
}

class LaylaApi(
    val jar: SessionJar,
    baseUrl: String,
    client: OkHttpClient? = null,
) {
    var base: String = baseUrl.trimEnd('/')
    private val http = client ?: OkHttpClient.Builder()
        .cookieJar(jar)
        .connectTimeout(20, TimeUnit.SECONDS)
        .readTimeout(120, TimeUnit.SECONDS)
        .build()

    fun login(email: String, password: String): JSONObject {
        val user = request(
            "POST",
            "/api/auth/login",
            JSONObject().put("email", email.trim()).put("password", password),
        ).obj()
        if (jar.sessionToken().isNullOrBlank()) {
            throw LaylaException(401, "Сервер не выдал сессию. Проверьте адрес Layla.")
        }
        return user
    }

    fun logout() {
        runCatching { request("POST", "/api/auth/logout") }
        jar.clear()
    }

    fun me() = request("GET", "/api/auth/me").obj()

    fun changePassword(current: String, next: String) = request(
        "POST",
        "/api/auth/change-password",
        JSONObject().put("current_password", current).put("new_password", next),
    ).obj()

    fun chats(domain: String) = request("GET", "/api/chats?domain=$domain").items()

    fun createChat(domain: String, title: String) = request(
        "POST",
        "/api/chats",
        JSONObject().put("domain", domain).put("title", title.ifBlank { "Новая задача" }),
    ).obj()

    fun chat(id: String) = request("GET", "/api/chats/$id").obj()

    fun send(chatId: String, content: String, mode: String, model: String?, providerId: String?) = request(
        "POST",
        "/api/chats/$chatId/messages",
        JSONObject().put("content", content).put("mode", mode).apply {
            if (!model.isNullOrBlank()) put("model", model)
            if (!providerId.isNullOrBlank()) put("provider_id", providerId)
        },
    ).obj()

    fun setServers(chatId: String, serverIds: List<String>) = request(
        "PUT",
        "/api/chats/$chatId/servers",
        JSONObject().put("server_ids", JSONArray(serverIds)),
    ).obj()

    fun servers() = request("GET", "/api/servers").items()

    fun addServer(host: String, port: Int, user: String, auth: String, secret: String) = request(
        "POST",
        "/api/servers",
        JSONObject()
            .put("host", host.trim())
            .put("port", port)
            .put("user", user.ifBlank { "root" })
            .put("auth", auth)
            .put(if (auth == "password") "password" else "private_key", secret),
    ).obj()

    fun testConnection(id: String) = request("POST", "/api/servers/$id/test-connection").obj()

    fun createProject(name: String) = request("POST", "/api/projects", JSONObject().put("name", name)).obj()

    fun projectFiles(id: String) = request("GET", "/api/projects/$id/files").items()

    fun git(id: String) = request("GET", "/api/projects/$id/git").obj()

    fun createEngagement(target: String) = request("POST", "/api/engagements", JSONObject().put("target", target)).obj()

    fun findings(id: String) = request("GET", "/api/engagements/$id/findings").items()

    fun reports(id: String) = request("GET", "/api/engagements/$id/reports").items()

    fun agentRuns(id: String) = request("GET", "/api/engagements/$id/agent/runs").items()

    fun createCase(subject: String, type: String) = request(
        "POST",
        "/api/osint/cases",
        JSONObject().put("subject", subject).put("subject_type", type),
    ).obj()

    fun artifacts(id: String) = request("GET", "/api/osint/cases/$id/artifacts").items()

    fun lookups(id: String) = request("GET", "/api/osint/cases/$id/lookups").items()

    fun createDesign(brand: String, notes: String) = request(
        "POST",
        "/api/designs/generate",
        JSONObject()
            .put("stack", "html")
            .put("brief", JSONObject().put("brand", brand).put("notes", notes).put("artifact_type", "Landing")),
    ).obj()

    fun design(id: String) = request("GET", "/api/designs/$id").obj()

    fun cancelJob(id: String) = request("POST", "/api/jobs/$id/cancel").obj()

    fun decide(jobId: String, approvalId: String, decision: String) = request(
        "POST",
        "/api/jobs/$jobId/decision",
        JSONObject().put("approval_id", approvalId).put("decision", decision),
    ).obj()

    fun createUser(email: String, name: String, admin: Boolean) = request(
        "POST",
        "/api/admin/users",
        JSONObject().put("email", email).put("display_name", name).put("is_admin", admin),
    ).obj()

    fun restoreChat(id: String) = request("POST", "/api/trash/chats/$id/restore")

    fun restoreProject(id: String) = request("POST", "/api/trash/projects/$id/restore")

    fun bootstrap() = request("GET", "/api/auth/bootstrap").obj()

    fun request(method: String, path: String, json: JSONObject? = null): ApiBody {
        val builder = Request.Builder().url(base + path).header("Accept", "application/json")
        val payload = json?.toString()?.toRequestBody(JSON)
        when (method) {
            "GET" -> builder.get()
            "POST" -> builder.post(payload ?: EMPTY)
            "PUT" -> builder.put(payload ?: EMPTY)
            "PATCH" -> builder.patch(payload ?: EMPTY)
            "DELETE" -> if (payload == null) builder.delete() else builder.delete(payload)
            else -> error("Неизвестный метод")
        }
        http.newCall(builder.build()).execute().use { response ->
            val text = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                val detail = runCatching { JSONObject(text).optString("detail") }.getOrDefault("")
                throw LaylaException(response.code, detail.ifBlank { text.ifBlank { response.message } })
            }
            return ApiBody(text)
        }
    }

    companion object {
        private val JSON = "application/json; charset=utf-8".toMediaType()
        private val EMPTY = ByteArray(0).toRequestBody(null)
    }
}

fun labelOf(row: JSONObject): String {
    val user = row.optString("user")
    val host = row.optString("host")
    if (user.isNotBlank() && host.isNotBlank()) return "$user@$host"
    for (key in listOf("title", "name", "target", "subject", "email", "brand", "action", "provider")) {
        val value = row.optString(key)
        if (value.isNotBlank() && value != "null") return value
    }
    val brief = row.optJSONObject("brief")?.optString("brand").orEmpty()
    if (brief.isNotBlank()) return brief
    return row.optString("id").ifBlank { "Запись" }
}
