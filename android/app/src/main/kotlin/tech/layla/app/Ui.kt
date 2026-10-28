package tech.layla.app

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import tech.layla.client.Catalog
import tech.layla.client.LaylaApi
import tech.layla.client.LaylaException
import tech.layla.client.Section
import tech.layla.client.Store
import tech.layla.client.labelOf

private val Ink = Color(0xFF0A0A0A)
private val Card = Color(0xFF1C1C1E)
private val Blue = Color(0xFF0A84FF)

private sealed interface Route
private data object Login : Route
private data object Home : Route
private data class Group(val id: String) : Route
private data class Listing(val sectionId: String) : Route
private data class Chat(val id: String, val title: String) : Route
private data class Record(val kind: String, val id: String, val title: String) : Route

@Composable
fun LaylaApp(api: LaylaApi, store: Store) {
    val scope = rememberCoroutineScope()
    var stack by remember { mutableStateOf(listOf<Route>(if (api.jar.sessionToken().isNullOrBlank()) Login else Home)) }
    var user by remember { mutableStateOf<JSONObject?>(null) }
    fun go(route: Route) { stack = stack + route }
    fun back() { if (stack.size > 1) stack = stack.dropLast(1) }
    MaterialTheme(colorScheme = darkColorScheme(primary = Blue, background = Ink, surface = Card)) {
        Surface(Modifier.fillMaxSize(), color = Ink) {
            when (val route = stack.last()) {
                Login -> LoginScreen(api, store) {
                    user = it
                    stack = listOf(Home)
                }
                Home -> HomeScreen(user, api, onOpen = ::go) {
                    scope.launch {
                        withContext(Dispatchers.IO) { runCatching { api.logout() } }
                        user = null
                        stack = listOf(Login)
                    }
                }
                is Group -> GroupScreen(route.id, ::back, ::go)
                is Listing -> ListScreen(api, Catalog.section(route.sectionId), ::back, ::go)
                is Chat -> ChatScreen(api, route.id, route.title, ::back)
                is Record -> RecordScreen(api, route, ::back)
            }
        }
    }
}

@Composable
private fun LoginScreen(api: LaylaApi, store: Store, onReady: (JSONObject) -> Unit) {
    var base by remember { mutableStateOf(store.get("base") ?: api.base) }
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Layla", style = MaterialTheme.typography.headlineLarge, color = Color.White)
        Text("Те же учётные записи, что в веб-версии. Введите адрес своего сервера.", color = Color(0xFFB5B5B5))
        Field("Адрес сервера", base) { base = it }
        Field("Почта", email) { email = it }
        Field("Пароль", password, password = true) { password = it }
        error?.let { Text(it, color = Color(0xFFFF8A80)) }
        Button(enabled = !busy && base.isNotBlank() && email.isNotBlank() && password.isNotBlank(), onClick = {
            busy = true
            error = null
            scope.launch {
                val result = withContext(Dispatchers.IO) {
                    runCatching {
                        api.base = base.trim().trimEnd('/')
                        store.put("base", api.base)
                        api.login(email, password)
                    }
                }
                busy = false
                result.onSuccess(onReady).onFailure { error = it.message }
            }
        }) { Text(if (busy) "Вход…" else "Войти") }
    }
}

@Composable
private fun HomeScreen(user: JSONObject?, api: LaylaApi, onOpen: (Route) -> Unit, onLogout: () -> Unit) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Column {
                Text("Layla", color = Color.White, style = MaterialTheme.typography.headlineMedium)
                Text(user?.optString("email").orEmpty().ifBlank { api.base }, color = Color(0xFF9A9A9A))
            }
            TextButton(onClick = onLogout) { Text("Выйти") }
        }
        Catalog.domains.forEach { domain ->
            Column(Modifier.fillMaxWidth().background(Card, RoundedCornerShape(16.dp)).clickable { onOpen(Group(domain.slug)) }.padding(16.dp)) {
                Text(domain.label, color = Color.White, style = MaterialTheme.typography.titleMedium)
                Text(domain.tagline, color = Color(0xFFB5B5B5))
            }
        }
        Column(Modifier.fillMaxWidth().background(Card, RoundedCornerShape(16.dp)).clickable { onOpen(Group("settings")) }.padding(16.dp)) {
            Text("Настройки", color = Color.White, style = MaterialTheme.typography.titleMedium)
            Text("Провайдеры, роли, пользователи, корзина и интеграции.", color = Color(0xFFB5B5B5))
        }
    }
}

@Composable
private fun GroupScreen(id: String, back: () -> Unit, open: (Route) -> Unit) {
    val title = if (id == "settings") "Настройки" else Catalog.domain(id).label
    val rows = if (id == "settings") Catalog.sectionsOf("settings") else Catalog.sectionsOf(id)
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        TextButton(onClick = back) { Text("Назад") }
        Text(title, color = Color.White, style = MaterialTheme.typography.headlineSmall)
        rows.forEach { section ->
            Text(section.title, color = Color.White, modifier = Modifier.fillMaxWidth().background(Card, RoundedCornerShape(12.dp)).clickable { open(Listing(section.id)) }.padding(14.dp))
        }
    }
}

@Composable
private fun ListScreen(api: LaylaApi, section: Section, back: () -> Unit, open: (Route) -> Unit) {
    var rows by remember { mutableStateOf<List<JSONObject>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(true) }
    var form by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    fun reload() {
        busy = true
        scope.launch {
            val result = withContext(Dispatchers.IO) { runCatching { api.request("GET", section.path).items(section.arrayKey) } }
            busy = false
            result.onSuccess { rows = it; error = null }.onFailure { error = (it as? LaylaException)?.message ?: it.message }
        }
    }
    LaunchedEffect(section.id) { reload() }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            TextButton(onClick = back) { Text("Назад") }
            if (section.form != null) TextButton(onClick = { form = !form }) { Text(if (form) "Закрыть" else "Создать") }
        }
        Text(section.title, color = Color.White, style = MaterialTheme.typography.headlineSmall)
        if (form && section.form != null) CreateForm(api, section) { form = false; reload() }
        if (busy) CircularProgressIndicator()
        error?.let { Text(it, color = Color(0xFFFF8A80)) }
        rows.forEach { row ->
            val id = row.optString("id")
            val kind = section.open
            val title = labelOf(row)
            Text(title, color = Color.White, modifier = Modifier.fillMaxWidth().background(Card, RoundedCornerShape(12.dp)).clickable {
                when (kind) {
                    "chat" -> if (id.isNotBlank()) open(Chat(id, title))
                    "trash-chat", "trash-project" -> if (id.isNotBlank()) open(Record(kind, id, title))
                    null -> Unit
                    else -> if (id.isNotBlank()) open(Record(kind, id, title))
                }
            }.padding(14.dp))
        }
        if (!busy && rows.isEmpty() && error == null) Text("Пока пусто.", color = Color(0xFF9A9A9A))
    }
}

@Composable
private fun CreateForm(api: LaylaApi, section: Section, onDone: () -> Unit) {
    var a by remember { mutableStateOf("") }
    var b by remember { mutableStateOf("") }
    var c by remember { mutableStateOf("root") }
    var d by remember { mutableStateOf("password") }
    var e by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        when (section.form) {
            "chat" -> Field("Название", a) { a = it }
            "project" -> Field("Название проекта", a) { a = it }
            "engagement" -> Field("Цель", a) { a = it }
            "case" -> Field("Субъект", a) { a = it }
            "design" -> {
                Field("Бренд", a) { a = it }
                Field("Заметки", b) { b = it }
            }
            "user" -> {
                Field("Почта", a) { a = it }
                Field("Имя", b) { b = it }
            }
            "server" -> {
                Field("Хост", a) { a = it }
                Field("Порт", b) { b = it }
                Field("Пользователь", c) { c = it }
                Field("key или password", d) { d = it }
                Field(if (d == "password") "Пароль" else "Приватный ключ", e, password = d == "password") { e = it }
            }
            "mcp" -> {
                Field("Имя", a) { a = it }
                Field("Команда или URL", b) { b = it }
            }
        }
        error?.let { Text(it, color = Color(0xFFFF8A80)) }
        Button(onClick = {
            scope.launch {
                val result = withContext(Dispatchers.IO) {
                    runCatching {
                        when (section.form) {
                            "chat" -> api.createChat(section.group, a)
                            "project" -> api.createProject(a)
                            "engagement" -> api.createEngagement(a)
                            "case" -> api.createCase(a, "domain")
                            "design" -> api.createDesign(a, b)
                            "user" -> api.createUser(a, b, false)
                            "server" -> api.addServer(a, b.toIntOrNull() ?: 22, c, if (d == "key") "key" else "password", e)
                            "mcp" -> api.request("POST", "/api/mcp/servers", JSONObject().put("name", a).put("command", b).put("transport", "stdio")).obj()
                            else -> JSONObject()
                        }
                    }
                }
                result.onSuccess { onDone() }.onFailure { error = it.message }
            }
        }) { Text("Сохранить") }
    }
}

@Composable
private fun ChatScreen(api: LaylaApi, id: String, title: String, back: () -> Unit) {
    var detail by remember { mutableStateOf<JSONObject?>(null) }
    var text by remember { mutableStateOf("") }
    var mode by remember { mutableStateOf("auto") }
    var error by remember { mutableStateOf<String?>(null) }
    var servers by remember { mutableStateOf<List<JSONObject>>(emptyList()) }
    var tick by remember { mutableStateOf(0) }
    val scope = rememberCoroutineScope()
    LaunchedEffect(id, tick) {
        while (true) {
            val loaded = withContext(Dispatchers.IO) { runCatching { api.chat(id) } }
            val chat = loaded.getOrElse { error = it.message; return@LaunchedEffect }
            detail = chat
            if (chat.optString("domain") == "agent") {
                servers = withContext(Dispatchers.IO) { runCatching { api.servers() }.getOrDefault(emptyList()) }
            }
            val status = chat.optJSONObject("last_job")?.optString("status")
            if (status != "queued" && status != "running") break
            kotlinx.coroutines.delay(1500)
        }
    }
    val messages = detail?.optJSONArray("messages")
    val chosen = detail?.optJSONArray("server_ids")?.let { array -> (0 until array.length()).map { array.getString(it) }.toSet() } ?: emptySet()
    Column(Modifier.fillMaxSize().padding(12.dp)) {
        TextButton(onClick = back) { Text("Назад") }
        Text(title, color = Color.White, style = MaterialTheme.typography.titleLarge)
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            listOf("auto" to "Авто", "confirm" to "С подтверждением", "plan" to "План", "review" to "Ревью").forEach { (value, label) ->
                FilterChip(selected = mode == value, onClick = { mode = value }, label = { Text(label) })
            }
        }
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState())) {
            if (messages != null) {
                for (index in 0 until messages.length()) {
                    val message = messages.getJSONObject(index)
                    Text("${message.optString("role")}: ${message.optString("content")}", color = Color.White, modifier = Modifier.padding(vertical = 6.dp))
                }
            }
            error?.let { Text(it, color = Color(0xFFFF8A80)) }
            val approval = detail?.optJSONObject("last_job")?.optJSONObject("result")?.optJSONObject("approval")
            val jobId = detail?.optJSONObject("last_job")?.optString("id").orEmpty()
            if (approval != null && jobId.isNotBlank()) {
                Row {
                    TextButton(onClick = { scope.launch { withContext(Dispatchers.IO) { runCatching { api.decide(jobId, approval.getString("id"), "approve") } }; tick++ } }) { Text("Применить") }
                    TextButton(onClick = { scope.launch { withContext(Dispatchers.IO) { runCatching { api.decide(jobId, approval.getString("id"), "reject") } }; tick++ } }) { Text("Отклонить") }
                }
            }
        }
        if (detail?.optString("domain") == "agent") {
            Text("Серверы этой задачи", color = Color(0xFFB5B5B5))
            servers.forEach { server ->
                val sid = server.getString("id")
                Row {
                    Checkbox(checked = sid in chosen, onCheckedChange = {
                        val next = if (sid in chosen) chosen - sid else chosen + sid
                        scope.launch { withContext(Dispatchers.IO) { runCatching { api.setServers(id, next.toList()) } }; tick++ }
                    })
                    Text(labelOf(server), color = Color.White, modifier = Modifier.padding(top = 12.dp))
                }
            }
        }
        Row {
            OutlinedTextField(text, { text = it }, modifier = Modifier.weight(1f), placeholder = { Text("Сообщение") })
            Button(onClick = {
                val content = text.trim()
                if (content.isEmpty()) return@Button
                text = ""
                scope.launch {
                    val result = withContext(Dispatchers.IO) { runCatching { api.send(id, content, mode, detail?.optString("model"), detail?.optString("provider_id")) } }
                    result.onFailure { error = it.message }
                    tick++
                }
            }, modifier = Modifier.padding(start = 8.dp)) { Text("OK") }
        }
    }
}

@Composable
private fun RecordScreen(api: LaylaApi, route: Record, back: () -> Unit) {
    var body by remember { mutableStateOf("Загрузка…") }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    LaunchedEffect(route.id) {
        val result = withContext(Dispatchers.IO) {
            runCatching {
                when (route.kind) {
                    "project" -> api.projectFiles(route.id).joinToString("\n") { it.toString(2) } + "\n\n" + api.git(route.id).toString(2)
                    "engagement" -> api.findings(route.id).joinToString("\n") { labelOf(it) }.ifBlank { "Находок нет." } +
                        "\n\nОтчёты\n" + api.reports(route.id).joinToString("\n") { labelOf(it) } +
                        "\n\nЗапуски\n" + api.agentRuns(route.id).joinToString("\n") { it.optString("status") + " " + it.optString("id") }
                    "case" -> api.artifacts(route.id).joinToString("\n") { labelOf(it) } + "\n\n" + api.lookups(route.id).joinToString("\n") { labelOf(it) }
                    "design" -> api.design(route.id).toString(2)
                    "server" -> api.testConnection(route.id).toString(2)
                    "provider" -> api.request("GET", "/api/providers/${route.id}/keys").text
                    "account" -> api.me().toString(2)
                    "job" -> api.request("GET", "/api/jobs/${route.id}").text
                    "trash-chat", "trash-project" -> route.title
                    else -> api.request("GET", "/api/auth/me").text
                }
            }
        }
        result.onSuccess { body = it }.onFailure { error = it.message; body = "" }
    }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp)) {
        TextButton(onClick = back) { Text("Назад") }
        Text(route.title, color = Color.White, style = MaterialTheme.typography.titleLarge)
        if (route.kind == "trash-chat" || route.kind == "trash-project") {
            Button(onClick = {
                scope.launch {
                    val result = withContext(Dispatchers.IO) {
                        runCatching { if (route.kind == "trash-chat") api.restoreChat(route.id) else api.restoreProject(route.id) }
                    }
                    result.onSuccess { body = "Восстановлено" }.onFailure { error = it.message }
                }
            }) { Text("Восстановить") }
        }
        if (route.kind == "job") {
            Button(onClick = {
                scope.launch {
                    val result = withContext(Dispatchers.IO) { runCatching { api.cancelJob(route.id).toString(2) } }
                    result.onSuccess { body = it }.onFailure { error = it.message }
                }
            }) { Text("Остановить") }
        }
        if (route.kind == "account") PasswordChange(api)
        error?.let { Text(it, color = Color(0xFFFF8A80)) }
        Text(body, color = Color(0xFFD0D0D0))
    }
}

@Composable
private fun PasswordChange(api: LaylaApi) {
    var current by remember { mutableStateOf("") }
    var next by remember { mutableStateOf("") }
    var note by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Field("Текущий пароль", current, password = true) { current = it }
        Field("Новый пароль", next, password = true) { next = it }
        Button(onClick = {
            scope.launch {
                val result = withContext(Dispatchers.IO) { runCatching { api.changePassword(current, next) } }
                note = result.fold({ "Пароль изменён и в вебе тоже" }, { it.message })
            }
        }) { Text("Сменить пароль") }
        note?.let { Text(it, color = Color.White) }
    }
}

@Composable
private fun Field(label: String, value: String, password: Boolean = false, onChange: (String) -> Unit) {
    OutlinedTextField(
        value = value,
        onValueChange = onChange,
        modifier = Modifier.fillMaxWidth(),
        label = { Text(label) },
        singleLine = !password || label != "Приватный ключ",
        visualTransformation = if (password) PasswordVisualTransformation() else androidx.compose.ui.text.input.VisualTransformation.None,
        keyboardOptions = if (label == "Порт") KeyboardOptions(keyboardType = KeyboardType.Number) else KeyboardOptions.Default,
    )
}
