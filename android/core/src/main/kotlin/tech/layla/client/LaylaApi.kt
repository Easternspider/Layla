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

    fun createChat(domain: String, title: String, projectId: String? = null, personaId: String? = null) = request(
        "POST",
        "/api/chats",
        JSONObject().put("domain", domain).put("title", title.ifBlank { "Новая задача" }).apply {
            if (!projectId.isNullOrBlank()) put("project_id", projectId)
            if (!personaId.isNullOrBlank()) put("persona_id", personaId)
        },
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

    fun createDesign(brand: String, notes: String, stack: String = "html") = request(
        "POST",
        "/api/designs/generate",
        JSONObject()
            .put("stack", stack.ifBlank { "html" })
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

    fun purgeChat(id: String) = request("DELETE", "/api/trash/chats/$id")

    fun purgeProject(id: String) = request("DELETE", "/api/trash/projects/$id")

    fun emptyTrash() = request("DELETE", "/api/trash")

    fun bootstrap() = request("GET", "/api/auth/bootstrap").obj()

    fun models() = request("GET", "/api/models").items()

    fun personas() = request("GET", "/api/personas").items()

    fun renameChat(id: String, title: String) = request(
        "PATCH",
        "/api/chats/$id",
        JSONObject().put("title", title),
    ).obj()

    fun deleteChat(id: String) = request("DELETE", "/api/chats/$id")

    fun compactChat(id: String) = request("POST", "/api/chats/$id/compact").obj()

    fun rollback(chatId: String, messageId: String) = request(
        "POST",
        "/api/chats/$chatId/messages/$messageId/rollback",
    ).obj()

    fun codeState(chatId: String) = request("GET", "/api/chats/$chatId/code-state").obj()

    fun answerCode(chatId: String, questionId: String, answer: String) = request(
        "POST",
        "/api/chats/$chatId/code-state/answer",
        JSONObject().put("question_id", questionId).put("answers", JSONObject().put("choice", JSONArray().put(answer))),
    ).obj()

    fun workerAction(chatId: String, workerId: String, action: String) = request(
        "POST",
        "/api/chats/$chatId/workers/$workerId/$action" + if (action == "discard") "?discard_changes=true" else "",
        JSONObject(),
    ).obj()

    fun readFile(projectId: String, path: String) = request(
        "GET",
        "/api/projects/$projectId/file?path=${encode(path)}",
    ).obj()

    fun writeFile(projectId: String, path: String, content: String, sha: String?) = request(
        "PUT",
        "/api/projects/$projectId/file",
        JSONObject().put("path", path).put("content", content).put("expected_sha256", sha ?: JSONObject.NULL),
    ).obj()

    fun deleteFile(projectId: String, path: String) = request(
        "DELETE",
        "/api/projects/$projectId/file?path=${encode(path)}",
    ).obj()

    fun deleteProject(id: String) = request("DELETE", "/api/projects/$id")

    fun importRepo(url: String, name: String) = request(
        "POST",
        "/api/projects/import",
        JSONObject().put("repo_url", url).put("name", name.ifBlank { JSONObject.NULL }),
    ).obj()

    fun gitInit(id: String) = request("POST", "/api/projects/$id/git/init").obj()

    fun gitCommit(id: String, message: String) = request(
        "POST",
        "/api/projects/$id/git/commit",
        JSONObject().put("message", message),
    ).obj()

    fun gitPush(id: String) = request("POST", "/api/projects/$id/git/push", JSONObject()).obj()

    fun gitPull(id: String) = request("POST", "/api/projects/$id/git/pull").obj()

    fun gitRemote(id: String, url: String) = request(
        "PUT",
        "/api/projects/$id/git/remote",
        JSONObject().put("url", url),
    ).obj()

    fun gitCredentials(host: String, token: String) = request(
        "PUT",
        "/api/git/credentials",
        JSONObject().put("host", host).put("token", token),
    ).obj()

    fun engagement(id: String) = request("GET", "/api/engagements/$id").obj()

    fun setScope(id: String, allow: List<String>, deny: List<String>) = request(
        "PUT",
        "/api/engagements/$id/scope",
        JSONObject().put("allow", JSONArray(allow)).put("deny", JSONArray(deny)),
    ).obj()

    fun confirmScope(id: String) = request("POST", "/api/engagements/$id/scope/confirm").obj()

    fun acceptAuthorization(id: String, sha: String) = request(
        "POST",
        "/api/engagements/$id/confirm",
        JSONObject().put("content_sha256", sha),
    ).obj()

    fun authorization(id: String) = request("GET", "/api/engagements/$id/authorization").obj()

    fun setOffensive(id: String, enabled: Boolean) = request(
        "PUT",
        "/api/engagements/$id/offensive",
        JSONObject().put("enabled", enabled),
    ).obj()

    fun setVenue(id: String, mode: String, egress: String) = request(
        "PUT",
        "/api/engagements/$id/venue",
        JSONObject().put("mode", mode).put("egress_route", egress),
    ).obj()

    fun addFinding(id: String, title: String, severity: String, description: String) = request(
        "POST",
        "/api/engagements/$id/findings",
        JSONObject().put("title", title).put("severity", severity).put("description", description).put("source", "manual"),
    ).obj()

    fun patchFinding(engagementId: String, findingId: String, status: String) = request(
        "PATCH",
        "/api/engagements/$engagementId/findings/$findingId",
        JSONObject().put("status", status),
    ).obj()

    fun generateReport(id: String) = request("POST", "/api/engagements/$id/reports/generate").obj()

    fun startAgent(id: String, task: String, mode: String) = request(
        "POST",
        "/api/engagements/$id/agent/runs",
        JSONObject().put("task", task).put("mode", mode),
    ).obj()

    fun stopAgent(runId: String) = request("POST", "/api/agent/runs/$runId/stop").obj()

    fun approveStep(stepId: String) = request("POST", "/api/agent/steps/$stepId/approve").obj()

    fun denyStep(stepId: String) = request("POST", "/api/agent/steps/$stepId/deny").obj()

    fun deleteEngagement(id: String) = request("DELETE", "/api/engagements/$id")

    fun addArtifact(caseId: String, title: String, summary: String, sourceUrl: String) = request(
        "POST",
        "/api/osint/cases/$caseId/artifacts",
        JSONObject().put("title", title).put("summary", summary).put("source_url", sourceUrl),
    ).obj()

    fun runLookup(caseId: String, provider: String, target: String) = request(
        "POST",
        "/api/osint/cases/$caseId/lookups",
        JSONObject().put("provider", provider).put("target", target),
    ).obj()

    fun deleteCase(id: String) = request("DELETE", "/api/osint/cases/$id")

    fun renameDesign(id: String, title: String) = request(
        "PATCH",
        "/api/designs/$id",
        JSONObject().put("title", title),
    ).obj()

    fun deleteDesign(id: String) = request("DELETE", "/api/designs/$id")

    fun deleteServer(id: String) = request("DELETE", "/api/servers/$id")

    fun createProvider(name: String, kind: String, baseUrl: String, apiKey: String) = request(
        "POST",
        "/api/providers",
        JSONObject().put("name", name).put("kind", kind).put("base_url", baseUrl.ifBlank { JSONObject.NULL }).put("api_key", apiKey.ifBlank { JSONObject.NULL }).put("enabled", true),
    ).obj()

    fun addKey(providerId: String, apiKey: String, label: String) = request(
        "POST",
        "/api/providers/$providerId/keys",
        JSONObject().put("api_key", apiKey).put("label", label.ifBlank { JSONObject.NULL }),
    ).obj()

    fun deleteKey(id: String) = request("DELETE", "/api/providers/keys/$id")

    fun deleteProvider(id: String) = request("DELETE", "/api/providers/$id")

    fun createPersona(name: String, instructions: String) = request(
        "POST",
        "/api/personas",
        JSONObject().put("name", name).put("instructions", instructions),
    ).obj()

    fun deletePersona(id: String) = request("DELETE", "/api/personas/$id")

    fun addKnowledge(title: String, content: String, domain: String) = request(
        "POST",
        "/api/knowledge",
        JSONObject().put("title", title).put("content", content).put("domain", domain.ifBlank { JSONObject.NULL }),
    ).obj()

    fun searchKnowledge(query: String) = request(
        "POST",
        "/api/knowledge/search",
        JSONObject().put("query", query).put("top_k", 8),
    ).items()

    fun deleteKnowledge(id: String) = request("DELETE", "/api/knowledge/$id")

    fun createCombo(name: String, models: List<String>) = request(
        "POST",
        "/api/combos",
        JSONObject().put("name", name).put("models", JSONArray(models)).put("enabled", true),
    ).obj()

    fun deleteCombo(id: String) = request("DELETE", "/api/combos/$id")

    fun saveTelegram(token: String, chatId: String, publicUrl: String): JSONObject {
        val body = JSONObject().put("enabled", true).put("control_enabled", true)
        if (token.isNotBlank()) body.put("bot_token", token)
        if (chatId.isNotBlank()) body.put("default_chat_id", chatId)
        if (publicUrl.isNotBlank()) body.put("public_url", publicUrl)
        return request("PUT", "/api/integrations/telegram", body).obj()
    }

    fun testTelegram() = request("POST", "/api/integrations/telegram/test", JSONObject()).obj()

    fun deleteTelegram() = request("DELETE", "/api/integrations/telegram")

    fun agentConfig() = request("GET", "/api/agent/config").obj()

    fun saveAgentConfig(current: JSONObject, preset: String) = request(
        "PUT",
        "/api/agent/config",
        JSONObject()
            .put("preset", preset.ifBlank { current.optString("preset").ifBlank { "minimal" } })
            .put("role_models", current.optJSONObject("role_models") ?: JSONObject())
            .put("budgets", current.optJSONObject("budgets") ?: JSONObject())
            .put("diagnostics", current.optJSONObject("diagnostics") ?: JSONObject())
            .put("context", current.optJSONObject("context") ?: JSONObject()),
    ).obj()

    fun updateUser(id: String, admin: Boolean?, active: Boolean?, reset: Boolean) = request(
        "PATCH",
        "/api/admin/users/$id",
        JSONObject().apply {
            if (admin != null) put("is_admin", admin)
            if (active != null) put("is_active", active)
            if (reset) put("reset_password", true)
        },
    ).obj()

    fun deleteUser(id: String) = request("DELETE", "/api/admin/users/$id")

    fun testMcp(id: String) = request("POST", "/api/mcp/servers/$id/test").obj()

    fun setMcpEnabled(id: String, enabled: Boolean) = request(
        "PATCH",
        "/api/mcp/servers/$id",
        JSONObject().put("enabled", enabled),
    ).obj()

    fun deleteMcp(id: String) = request("DELETE", "/api/mcp/servers/$id")

    fun saveIntelKey(provider: String, apiKey: String) = request(
        "PUT",
        "/api/integrations/intelligence/$provider",
        JSONObject().put("api_key", apiKey),
    ).obj()

    fun installLanguage(language: String, version: String) = request(
        "POST",
        "/api/sandbox/languages",
        JSONObject().put("language", language).put("version", version),
    ).obj()

    fun removeLanguage(language: String, version: String) = request(
        "DELETE",
        "/api/sandbox/languages",
        JSONObject().put("language", language).put("version", version),
    ).obj()

    fun auditCsv() = request("GET", "/api/audit/export.csv").text

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

        fun encode(value: String) = java.net.URLEncoder.encode(value, Charsets.UTF_8.name())
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
