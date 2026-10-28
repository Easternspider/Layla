package tech.layla.app

import android.webkit.WebView
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import tech.layla.client.LaylaApi
import tech.layla.client.labelOf

private data class Loaded(val text: String, val html: String = "", val raw: JSONObject? = null)

@Composable
fun WorkScreen(api: LaylaApi, route: Record, back: () -> Unit) {
    var body by remember { mutableStateOf("Загрузка…") }
    var html by remember { mutableStateOf("") }
    var raw by remember { mutableStateOf<JSONObject?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var tick by remember { mutableIntStateOf(0) }
    var a by remember { mutableStateOf("") }
    var b by remember { mutableStateOf("") }
    var c by remember { mutableStateOf("") }
    val scope = rememberCoroutineScope()
    fun go(refresh: Boolean = true, block: () -> Any?) {
        scope.launch {
            val result = withContext(Dispatchers.IO) { runCatching { block() } }
            result.onSuccess { value ->
                when (value) {
                    is JSONObject -> body = value.toString(2)
                    is String -> if (value.isNotBlank()) body = value
                }
                if (refresh) tick++
            }.onFailure { error = it.message }
        }
    }
    LaunchedEffect(route.kind, route.id, tick) {
        val result = withContext(Dispatchers.IO) { runCatching { load(api, route) } }
        result.onSuccess {
            body = it.text
            html = it.html
            raw = it.raw
            error = null
        }.onFailure { error = it.message }
    }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        TextButton(onClick = back) { Text("Назад") }
        Text(route.title, color = Color.White, style = MaterialTheme.typography.titleLarge)
        error?.let { Text(it, color = Color(0xFFFF8A80)) }
        when (route.kind) {
            "project" -> {
                Field("Путь файла", a) { a = it }
                Field("Содержимое", b) { b = it }
                Field("Сообщение коммита или URL remote", c) { c = it }
                Row {
                    TextButton(onClick = { go { val file = api.readFile(route.id, a); b = file.optString("content") } }) { Text("Открыть") }
                TextButton(onClick = {
                    go {
                        val sha = runCatching { api.readFile(route.id, a).optString("sha256") }.getOrNull()?.takeIf { it.length == 64 }
                        api.writeFile(route.id, a, b, sha)
                    }
                }) { Text("Записать") }
                    TextButton(onClick = { go { api.deleteFile(route.id, a) } }) { Text("Удалить файл") }
                }
                Row {
                    TextButton(onClick = { go { api.gitInit(route.id) } }) { Text("git init") }
                    TextButton(onClick = { go { api.gitCommit(route.id, c) } }) { Text("Коммит") }
                    TextButton(onClick = { go { api.gitPush(route.id) } }) { Text("Push") }
                    TextButton(onClick = { go { api.gitPull(route.id) } }) { Text("Pull") }
                }
                TextButton(onClick = { go { api.gitRemote(route.id, c) } }) { Text("Сохранить remote") }
                TextButton(onClick = { go(false) { api.createChat("code", route.title, route.id) } }) { Text("Чат по этому проекту") }
                TextButton(onClick = { go(false) { api.deleteProject(route.id); "Проект удалён" } }) { Text("Удалить проект") }
            }
            "engagement" -> {
                Field("Scope allow, по строке", a) { a = it }
                Field("Scope deny, по строке", b) { b = it }
                Field("Находка, задача агента или mode/egress", c) { c = it }
                TextButton(onClick = { go { api.setScope(route.id, lines(a), lines(b)) } }) { Text("Сохранить scope") }
                TextButton(onClick = { go { api.confirmScope(route.id) } }) { Text("Подтвердить scope") }
                TextButton(onClick = {
                    val sha = raw?.optString("content_sha256").orEmpty()
                    go { api.acceptAuthorization(route.id, sha) }
                }) { Text("Принять декларацию") }
                TextButton(onClick = { go { api.setOffensive(route.id, true) } }) { Text("Включить offensive") }
                TextButton(onClick = { go { api.setOffensive(route.id, false) } }) { Text("Выключить offensive") }
                TextButton(onClick = {
                    val parts = c.split("/").map { it.trim() }
                    go { api.setVenue(route.id, parts.getOrElse(0) { "analysis_only" }.ifBlank { "analysis_only" }, parts.getOrElse(1) { "inherit" }.ifBlank { "inherit" }) }
                }) { Text("Venue mode/egress") }
                TextButton(onClick = { go { api.addFinding(route.id, c.ifBlank { "Находка" }, "medium", c) } }) { Text("Добавить находку") }
                TextButton(onClick = { go { api.generateReport(route.id) } }) { Text("Собрать отчёт") }
                TextButton(onClick = { go { api.startAgent(route.id, c, "interactive") } }) { Text("Запустить агента") }
                TextButton(onClick = { go { api.deleteEngagement(route.id) } }) { Text("Удалить engagement") }
            }
            "case" -> {
                Field("Заметка", a) { a = it }
                Field("Ссылка на источник", b) { b = it }
                Field("Провайдер shodan/virustotal/securitytrails/urlscan и цель", c) { c = it }
                TextButton(onClick = { go { api.addArtifact(route.id, a.ifBlank { "Заметка" }, a.ifBlank { "Заметка" }, b) } }) { Text("Добавить артефакт") }
                TextButton(onClick = {
                    val parts = c.split(" ", limit = 2)
                    go { api.runLookup(route.id, parts[0], parts.getOrElse(1) { "" }) }
                }) { Text("Запросить источник") }
                TextButton(onClick = { go { api.deleteCase(route.id) } }) { Text("Удалить кейс") }
            }
            "design" -> {
                Field("Новое название", a) { a = it }
                TextButton(onClick = { go { api.renameDesign(route.id, a) } }) { Text("Переименовать") }
                TextButton(onClick = { go { api.deleteDesign(route.id) } }) { Text("Удалить") }
                if (html.isNotBlank()) {
                    AndroidView(
                        factory = { context ->
                            WebView(context).apply {
                                settings.javaScriptEnabled = true
                                settings.allowFileAccess = false
                            }
                        },
                        update = { view -> view.loadDataWithBaseURL("https://layla.local/", html, "text/html", "utf-8", null) },
                        modifier = Modifier.fillMaxWidth().height(420.dp),
                    )
                }
            }
            "server" -> TextButton(onClick = { go(false) { api.deleteServer(route.id); "Сервер удалён" } }) { Text("Удалить сервер") }
            "provider" -> {
                Field("Новый API-ключ", a, password = true) { a = it }
                Field("Подпись ключа", b) { b = it }
                TextButton(onClick = { go { api.addKey(route.id, a, b) } }) { Text("Добавить ключ") }
                Field("ID ключа для удаления", c) { c = it }
                TextButton(onClick = { go { api.deleteKey(c) } }) { Text("Удалить ключ") }
                TextButton(onClick = { go { api.deleteProvider(route.id) } }) { Text("Удалить провайдера") }
            }
            "persona" -> TextButton(onClick = { go { api.deletePersona(route.id) } }) { Text("Удалить роль") }
            "knowledge" -> {
                Field("Запрос", a) { a = it }
                TextButton(onClick = {
                    scope.launch {
                        val result = withContext(Dispatchers.IO) { runCatching { api.searchKnowledge(a).joinToString("\n\n") { it.optString("content") } } }
                        result.onSuccess { body = it.ifBlank { "Ничего не найдено" } }.onFailure { error = it.message }
                    }
                }) { Text("Найти в базе") }
                TextButton(onClick = { go(false) { api.deleteKnowledge(route.id); "Документ удалён" } }) { Text("Удалить документ") }
            }
            "user" -> {
                TextButton(onClick = { go { api.updateUser(route.id, admin = true, active = null, reset = false) } }) { Text("Сделать админом") }
                TextButton(onClick = { go { api.updateUser(route.id, admin = false, active = null, reset = false) } }) { Text("Снять админа") }
                TextButton(onClick = { go { api.updateUser(route.id, admin = null, active = false, reset = false) } }) { Text("Отключить") }
                TextButton(onClick = { go(false) { api.updateUser(route.id, admin = null, active = true, reset = true) } }) { Text("Сбросить пароль") }
                TextButton(onClick = { go(false) { api.deleteUser(route.id); "Пользователь удалён" } }) { Text("Удалить") }
            }
            "mcp" -> {
                TextButton(onClick = { go { api.testMcp(route.id) } }) { Text("Проверить") }
                TextButton(onClick = { go { api.setMcpEnabled(route.id, true) } }) { Text("Включить") }
                TextButton(onClick = { go { api.setMcpEnabled(route.id, false) } }) { Text("Выключить") }
                TextButton(onClick = { go { api.deleteMcp(route.id) } }) { Text("Удалить") }
            }
            "telegram" -> {
                Field("Токен BotFather", a, password = true) { a = it }
                Field("Chat id", b) { b = it }
                Field("HTTPS-адрес Layla", c) { c = it }
                TextButton(onClick = { go { api.saveTelegram(a, b, c) } }) { Text("Сохранить") }
                TextButton(onClick = { go { api.testTelegram() } }) { Text("Тест") }
                TextButton(onClick = { go { api.deleteTelegram() } }) { Text("Отключить") }
            }
            "agent-config" -> {
                Field("minimal, pulse или constellation", a) { a = it }
                TextButton(onClick = { go { api.saveAgentConfig(raw ?: JSONObject(), a.ifBlank { "minimal" }) } }) { Text("Сохранить стиль") }
            }
            "sandbox" -> {
                Field("Язык", a) { a = it }
                Field("Версия", b) { b = it }
                TextButton(onClick = { go { api.installLanguage(a, b) } }) { Text("Установить") }
                TextButton(onClick = { go { api.removeLanguage(a, b) } }) { Text("Удалить") }
            }
            "intel" -> {
                Field("API-ключ", a, password = true) { a = it }
                TextButton(onClick = { go { api.saveIntelKey(route.id, a) } }) { Text("Сохранить ключ") }
            }
            "combo" -> TextButton(onClick = { go { api.deleteCombo(route.id) } }) { Text("Удалить combo") }
            "trash-chat" -> {
                Button(onClick = { go { api.restoreChat(route.id) } }) { Text("Восстановить") }
                TextButton(onClick = { go { api.purgeChat(route.id) } }) { Text("Удалить навсегда") }
            }
            "trash-project" -> {
                Button(onClick = { go { api.restoreProject(route.id) } }) { Text("Восстановить") }
                TextButton(onClick = { go { api.purgeProject(route.id) } }) { Text("Удалить навсегда") }
            }
            "job" -> TextButton(onClick = { go { api.cancelJob(route.id) } }) { Text("Остановить") }
            "account" -> PasswordChange(api)
            "audit" -> TextButton(onClick = {
                scope.launch {
                    val result = withContext(Dispatchers.IO) { runCatching { api.auditCsv() } }
                    result.onSuccess { body = it }.onFailure { error = it.message }
                }
            }) { Text("Показать CSV") }
            "health", "meta" -> Text("Те же данные, что в веб-настройках.", color = Color(0xFFB5B5B5))
        }
        if (route.kind == "engagement") {
            TextButton(onClick = {
                scope.launch {
                    val result = withContext(Dispatchers.IO) { runCatching { api.stopAgent(a) } }
                    result.onFailure { error = it.message }.onSuccess { tick++ }
                }
            }) { Text("Остановить запуск (id в поле allow)") }
            TextButton(onClick = { go { api.approveStep(b) } }) { Text("Одобрить шаг (id в deny)") }
            TextButton(onClick = { go { api.denyStep(b) } }) { Text("Отклонить шаг") }
        }
        Text(body, color = Color(0xFFD0D0D0))
    }
}

private fun lines(text: String) = text.split('\n').map { it.trim() }.filter { it.isNotEmpty() }

private fun load(api: LaylaApi, route: Record): Loaded = when (route.kind) {
    "project" -> Loaded(api.projectFiles(route.id).joinToString("\n") { "${if (it.optBoolean("is_dir")) "dir" else "file"} ${it.optString("path")}" } + "\n\n" + api.git(route.id).toString(2))
    "engagement" -> {
        val auth = runCatching { api.authorization(route.id) }.getOrElse { JSONObject().put("reason", it.message) }
        val findings = api.findings(route.id).joinToString("\n") { "${it.optString("severity")} ${it.optString("status")} ${labelOf(it)} ${it.optString("id")}" }
        val reports = api.reports(route.id).joinToString("\n") { "${it.optString("format")} ${it.optString("status")} ${it.optString("id")}" }
        val runs = api.agentRuns(route.id).joinToString("\n") { "${it.optString("status")} ${it.optString("id")} ${it.optString("task")}" }
        Loaded(api.engagement(route.id).toString(2) + "\n\nАвторизация\n" + auth.toString(2) + "\n\nНаходки\n" + findings.ifBlank { "нет" } + "\n\nОтчёты\n" + reports.ifBlank { "нет" } + "\n\nЗапуски\n" + runs.ifBlank { "нет" }, raw = auth)
    }
    "case" -> Loaded(api.artifacts(route.id).joinToString("\n") { labelOf(it) }.ifBlank { "Артефактов нет." } + "\n\nЗапросы\n" + api.lookups(route.id).joinToString("\n") { "${it.optString("provider")} ${it.optString("status")} ${it.optString("target")}" })
    "design" -> {
        val design = api.design(route.id)
        val files = design.optJSONArray("files")
        val page = if (files == null) "" else (0 until files.length()).map { files.getJSONObject(it) }.firstOrNull { it.optString("language") == "html" || it.optString("name").endsWith(".html") }?.optString("content").orEmpty()
        Loaded(design.toString(2).take(8000), html = page)
    }
    "server" -> Loaded(api.testConnection(route.id).toString(2))
    "provider" -> Loaded(api.request("GET", "/api/providers/${route.id}/keys").text)
    "account" -> Loaded(api.me().toString(2))
    "job" -> Loaded(api.request("GET", "/api/jobs/${route.id}").text)
    "agent-config" -> {
        val config = api.agentConfig()
        Loaded(config.toString(2), raw = config)
    }
    "sandbox" -> Loaded(api.request("GET", "/api/sandbox/status").text + "\n\n" + api.request("GET", "/api/sandbox/languages").text)
    "telegram", "meta", "health" -> Loaded(api.request("GET", when (route.kind) {
        "telegram" -> "/api/integrations/telegram"
        "meta" -> "/api/meta"
        else -> "/api/providers/accounts/health"
    }).text)
    "audit" -> Loaded(api.request("GET", "/api/audit").items().firstOrNull { it.optString("id") == route.id }?.toString(2) ?: "Запись не найдена")
    "persona" -> Loaded(api.personas().firstOrNull { it.optString("id") == route.id }?.toString(2) ?: route.title)
    "knowledge" -> Loaded(route.title)
    "user" -> Loaded(api.request("GET", "/api/admin/users").items().firstOrNull { it.optString("id") == route.id }?.toString(2) ?: route.title)
    "mcp" -> Loaded(route.title)
    "intel" -> Loaded(api.request("GET", "/api/integrations/intelligence").items().firstOrNull { it.optString("provider") == route.id }?.toString(2) ?: route.title)
    "combo" -> Loaded(route.title)
    "trash-chat", "trash-project" -> Loaded(route.title)
    else -> Loaded(route.title)
}
