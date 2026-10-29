package tech.layla.app

import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Shapes
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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
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

internal sealed interface Route
internal data object Login : Route
internal data object Home : Route
internal data class Group(val id: String) : Route
internal data class Listing(val sectionId: String) : Route
internal data class Chat(val id: String, val title: String) : Route
internal data class Record(val kind: String, val id: String, val title: String) : Route

@Composable
fun LaylaApp(api: LaylaApi, store: Store) {
    val scope = rememberCoroutineScope()
    var stack by remember { mutableStateOf(listOf<Route>(if (api.jar.sessionToken().isNullOrBlank()) Login else Home)) }
    var user by remember { mutableStateOf<JSONObject?>(null) }
    fun go(route: Route) { stack = stack + route }
    fun back() { if (stack.size > 1) stack = stack.dropLast(1) }
    MaterialTheme(
        colorScheme = darkColorScheme(
            primary = Blue,
            onPrimary = Color.White,
            background = Ink,
            onBackground = Color.White,
            surface = Card,
            onSurface = Color.White,
            surfaceVariant = Raised,
            outline = Line,
            error = Danger,
        ),
        shapes = Shapes(
            extraSmall = RoundedCornerShape(8.dp),
            small = RoundedCornerShape(10.dp),
            medium = RoundedCornerShape(14.dp),
            large = RoundedCornerShape(18.dp),
            extraLarge = RoundedCornerShape(24.dp),
        ),
    ) {
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
                is Record -> WorkScreen(api, route, ::back)
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
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 24.dp, vertical = 36.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Wordmark()
        Text("Ваши идеи.", color = Color.White, fontSize = 34.sp, fontWeight = FontWeight.SemiBold, letterSpacing = (-0.8).sp)
        Text("Новые возможности.", color = Color(0xFF99C9FF), fontSize = 34.sp, fontWeight = FontWeight.SemiBold, letterSpacing = (-0.8).sp)
        Text("Те же учётные записи, что на сайте. Укажите адрес своего сервера.", color = Muted, fontSize = 15.sp, lineHeight = 22.sp)
        Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Catalog.domains.forEach { domain ->
                Text(
                    domain.label,
                    color = domainColor(domain.slug),
                    fontSize = 12.sp,
                    modifier = Modifier.background(Card, RoundedCornerShape(999.dp)).padding(horizontal = 12.dp, vertical = 8.dp),
                )
            }
        }
        Panel {
            Text("Войти", color = Color.White, fontWeight = FontWeight.SemiBold, fontSize = 18.sp)
            Text("Рады видеть вас в Layla.", color = Muted, fontSize = 14.sp)
            Field("Адрес сервера", base) { base = it }
            Field("Почта", email) { email = it }
            Field("Пароль", password, password = true) { password = it }
            error?.let { Text(it, color = Danger, fontSize = 14.sp) }
            Button(
                enabled = !busy && base.isNotBlank() && email.isNotBlank() && password.isNotBlank(),
                onClick = {
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
                },
                modifier = Modifier.fillMaxWidth().height(48.dp),
                shape = RoundedCornerShape(999.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Blue, contentColor = Color.White, disabledContainerColor = Blue.copy(alpha = 0.35f)),
            ) { Text(if (busy) "Вход…" else "Войти", fontWeight = FontWeight.SemiBold) }
        }
        Text("Новые учётные записи создаёт администратор в разделе «Пользователи».", color = Color(0xFF636366), fontSize = 12.sp)
    }
}

@Composable
private fun HomeScreen(user: JSONObject?, api: LaylaApi, onOpen: (Route) -> Unit, onLogout: () -> Unit) {
    val initial = (user?.optString("display_name").orEmpty().ifBlank { user?.optString("email").orEmpty() }.ifBlank { "L" }).take(1).uppercase()
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp, vertical = 18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
            Wordmark()
            Avatar(initial, onLogout)
        }
        Text(user?.optString("email").orEmpty().ifBlank { api.base }, color = Muted, fontSize = 13.sp)
        Catalog.domains.forEach { domain ->
            DomainTile(domain.slug, domain.label, domain.tagline) { onOpen(Group(domain.slug)) }
        }
        DomainTile("settings", "Настройки", "Провайдеры, роли, пользователи, корзина и интеграции.") { onOpen(Group("settings")) }
    }
}

@Composable
private fun GroupScreen(id: String, back: () -> Unit, open: (Route) -> Unit) {
    val title = if (id == "settings") "Настройки" else Catalog.domain(id).label
    val rows = if (id == "settings") Catalog.sectionsOf("settings") else Catalog.sectionsOf(id)
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        BackBar(title, back)
        Text(if (id == "settings") "Как в веб-версии" else Catalog.domain(id).tagline, color = Muted, fontSize = 13.sp, modifier = Modifier.padding(horizontal = 12.dp))
        rows.forEach { section ->
            ListTile(section.title) { open(Listing(section.id)) }
        }
    }
}

@Composable
private fun ListScreen(api: LaylaApi, section: Section, back: () -> Unit, open: (Route) -> Unit) {
    var rows by remember { mutableStateOf<List<JSONObject>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(true) }
    var form by remember { mutableStateOf(false) }
    var csv by remember(section.id) { mutableStateOf<String?>(null) }
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
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        BackBar(section.title, back) {
            if (section.form != null) TextButton(onClick = { form = !form }) { Text(if (form) "Закрыть" else "Создать", color = Blue) }
        }
        if (form && section.form != null) Panel { CreateForm(api, section) { form = false; reload() } }
        if (busy) CircularProgressIndicator(color = Blue, modifier = Modifier.padding(16.dp))
        error?.let { Text(it, color = Danger, modifier = Modifier.padding(horizontal = 8.dp)) }
        rows.forEach { row ->
            val id = row.optString("id").ifBlank { row.optString("provider") }
            val kind = section.open
            val title = labelOf(row)
            val singleton = kind in setOf("telegram", "agent-config", "sandbox", "meta", "health")
            val openRow: (() -> Unit)? = when (kind) {
                "chat" -> if (id.isNotBlank()) ({ open(Chat(id, title)) }) else null
                null -> null
                else -> if (singleton || id.isNotBlank()) ({ open(Record(kind, id, title)) }) else null
            }
            ListTile(title, openRow)
        }
        if (section.id == "settings-security") {
            Button(
                onClick = {
                    scope.launch {
                        val result = withContext(Dispatchers.IO) { runCatching { api.auditCsv() } }
                        result.onSuccess { csv = it }.onFailure { error = it.message }
                    }
                },
                shape = RoundedCornerShape(999.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Blue),
            ) { Text("Экспорт CSV") }
            csv?.let { Text(it, color = Soft, modifier = Modifier.padding(8.dp)) }
        }
        if (!busy && rows.isEmpty() && error == null) Text("Пока пусто.", color = Muted, modifier = Modifier.padding(12.dp))
    }
}

@Composable
private fun CreateForm(api: LaylaApi, section: Section, onDone: () -> Unit) {
    var a by remember { mutableStateOf("") }
    var b by remember { mutableStateOf("") }
    var c by remember { mutableStateOf("") }
    var d by remember { mutableStateOf("password") }
    var e by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        when (section.form) {
            "chat" -> Field("Название", a) { a = it }
            "project" -> Field("Название проекта", a) { a = it }
            "engagement" -> Field("Цель", a) { a = it }
            "case" -> {
                Field("Субъект", a) { a = it }
                Field("domain, person или company", b) { b = it }
            }
            "design" -> {
                Field("Бренд", a) { a = it }
                Field("Заметки", b) { b = it }
                Field("Стек: html, react или vue", c) { c = it }
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
            "import" -> {
                Field("Git URL", a) { a = it }
                Field("Название", b) { b = it }
            }
            "provider" -> {
                Field("Название", a) { a = it }
                Field("openai_compatible, anthropic или custom", b) { b = it }
                Field("Base URL", c) { c = it }
                Field("API-ключ", e, password = true) { e = it }
            }
            "persona" -> {
                Field("Название", a) { a = it }
                Field("Инструкции", b) { b = it }
            }
            "knowledge" -> {
                Field("Название", a) { a = it }
                Field("Текст", b) { b = it }
                Field("Домен, если нужен", c) { c = it }
            }
            "combo" -> {
                Field("Название", a) { a = it }
                Field("Модели через запятую", b) { b = it }
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
                            "case" -> api.createCase(a, b.ifBlank { "domain" })
                            "design" -> api.createDesign(a, b, c.ifBlank { "html" })
                            "user" -> api.createUser(a, b, false)
                            "server" -> api.addServer(a, b.toIntOrNull() ?: 22, c, if (d == "key") "key" else "password", e)
                            "mcp" -> api.request("POST", "/api/mcp/servers", JSONObject().put("name", a).put("command", b).put("transport", "stdio")).obj()
                            "import" -> api.importRepo(a, b)
                            "provider" -> api.createProvider(a, b.ifBlank { "openai_compatible" }, c, e)
                            "persona" -> api.createPersona(a, b)
                            "knowledge" -> api.addKnowledge(a, b, c)
                            "combo" -> api.createCombo(a, b.split(",").map { it.trim() }.filter { it.isNotEmpty() })
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
    var model by remember { mutableStateOf("") }
    var rename by remember { mutableStateOf(title) }
    var error by remember { mutableStateOf<String?>(null) }
    var servers by remember { mutableStateOf<List<JSONObject>>(emptyList()) }
    var more by remember { mutableStateOf(false) }
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
    Column(Modifier.fillMaxSize().padding(horizontal = 12.dp, vertical = 6.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        BackBar(title, back) {
            TextButton(onClick = { more = !more }) { Text(if (more) "Скрыть" else "Ещё", color = Blue) }
        }
        if (more) {
            Field("Название", rename) { rename = it }
            Field("Модель, если не та, что у чата", model) { model = it }
            Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                TextButton(onClick = {
                    scope.launch {
                        val result = withContext(Dispatchers.IO) { runCatching { api.renameChat(id, rename.ifBlank { title }) } }
                        result.onFailure { error = it.message }
                        tick++
                    }
                }) { Text("Переименовать", color = Blue) }
                TextButton(onClick = {
                    scope.launch {
                        val result = withContext(Dispatchers.IO) { runCatching { api.compactChat(id) } }
                        result.onFailure { error = it.message }
                        tick++
                    }
                }) { Text("Сжать", color = Blue) }
                TextButton(onClick = {
                    scope.launch {
                        val result = withContext(Dispatchers.IO) { runCatching { api.deleteChat(id) } }
                        result.onSuccess { back() }.onFailure { error = it.message }
                    }
                }) { Text("В корзину", color = Danger) }
            }
        }
        Segments(listOf("auto" to "Авто", "confirm" to "Подтверждение", "plan" to "План", "review" to "Ревью"), mode) { mode = it }
        Column(Modifier.weight(1f).verticalScroll(rememberScrollState())) {
            if (messages == null || messages.length() == 0) {
                Column(Modifier.fillMaxWidth().padding(top = 48.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    BrandMark(56.dp)
                    Text("Что сделаем сегодня?", color = Color.White, fontSize = 22.sp, fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(top = 16.dp))
                    Text("Опишите задачу. История сохранится и на сайте.", color = Muted, fontSize = 14.sp, modifier = Modifier.padding(top = 8.dp, start = 24.dp, end = 24.dp))
                }
            } else {
                for (index in 0 until messages.length()) {
                    val message = messages.getJSONObject(index)
                    ChatBubble(message.optString("role"), message.optString("content"))
                    val messageId = message.optString("id")
                    if (message.optString("role") == "assistant" && messageId.isNotBlank()) {
                        TextButton(onClick = {
                            scope.launch {
                                val result = withContext(Dispatchers.IO) { runCatching { api.rollback(id, messageId) } }
                                result.onFailure { error = it.message }
                                tick++
                            }
                        }) { Text("Откатить", color = Muted, fontSize = 12.sp) }
                    }
                }
            }
            error?.let { Text(it, color = Danger) }
            val job = detail?.optJSONObject("last_job")
            val jobStatus = job?.optString("status")
            val approval = job?.optJSONObject("result")?.optJSONObject("approval")
            if (job != null && (jobStatus == "queued" || jobStatus == "running")) {
                TextButton(onClick = {
                    scope.launch {
                        withContext(Dispatchers.IO) { runCatching { api.cancelJob(job.getString("id")) } }
                        tick++
                    }
                }) { Text("Остановить задачу", color = Blue) }
            }
            if (detail?.optString("domain") == "code") CodeTools(api, id) { error = it; tick++ }
            val jobId = job?.optString("id").orEmpty()
            if (approval != null && jobId.isNotBlank()) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(
                        onClick = { scope.launch { withContext(Dispatchers.IO) { runCatching { api.decide(jobId, approval.getString("id"), "approve") } }; tick++ } },
                        shape = RoundedCornerShape(999.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = Blue),
                    ) { Text("Применить") }
                    TextButton(onClick = { scope.launch { withContext(Dispatchers.IO) { runCatching { api.decide(jobId, approval.getString("id"), "reject") } }; tick++ } }) { Text("Отклонить", color = Muted) }
                }
            }
        }
        if (detail?.optString("domain") == "agent") {
            Text("Серверы этой задачи", color = Muted, fontSize = 12.sp)
            servers.forEach { server ->
                val sid = server.getString("id")
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(checked = sid in chosen, onCheckedChange = {
                        val next = if (sid in chosen) chosen - sid else chosen + sid
                        scope.launch { withContext(Dispatchers.IO) { runCatching { api.setServers(id, next.toList()) } }; tick++ }
                    })
                    Text(labelOf(server), color = Color.White)
                }
            }
        }
        Row(
            Modifier.fillMaxWidth().background(Card, RoundedCornerShape(22.dp)).padding(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            OutlinedTextField(
                text,
                { text = it },
                modifier = Modifier.weight(1f),
                placeholder = { Text("Сообщение", color = Muted) },
                colors = fieldColors(),
                shape = RoundedCornerShape(16.dp),
            )
            Button(
                onClick = {
                    val content = text.trim()
                    if (content.isEmpty()) return@Button
                    text = ""
                    scope.launch {
                        val result = withContext(Dispatchers.IO) {
                            runCatching {
                                val chosenModel = model.ifBlank { detail?.optString("model") }
                                api.send(id, content, mode, chosenModel, detail?.optString("provider_id"))
                            }
                        }
                        result.onFailure { error = it.message }
                        tick++
                    }
                },
                modifier = Modifier.padding(start = 8.dp).size(44.dp),
                shape = RoundedCornerShape(999.dp),
                contentPadding = androidx.compose.foundation.layout.PaddingValues(0.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Blue),
            ) { Text("↑", fontSize = 18.sp) }
        }
    }
}

@Composable
private fun CodeTools(api: LaylaApi, chatId: String, onError: (String?) -> Unit) {
    var state by remember { mutableStateOf<JSONObject?>(null) }
    var question by remember { mutableStateOf("") }
    var answer by remember { mutableStateOf("") }
    var worker by remember { mutableStateOf("") }
    val scope = rememberCoroutineScope()
    LaunchedEffect(chatId) {
        state = withContext(Dispatchers.IO) { runCatching { api.codeState(chatId) }.getOrNull() }
    }
    Text("Код: состояние, вопрос агенту, воркер", color = Muted, fontSize = 13.sp)
    state?.let { Text(it.toString(2).take(2000), color = Soft, fontSize = 12.sp) }
    Field("ID вопроса", question) { question = it }
    Field("Ответ", answer) { answer = it }
    TextButton(onClick = {
        scope.launch {
            val result = withContext(Dispatchers.IO) { runCatching { api.answerCode(chatId, question, answer) } }
            result.onSuccess { state = it; onError(null) }.onFailure { onError(it.message) }
        }
    }) { Text("Ответить") }
    Field("ID воркера", worker) { worker = it }
    Row {
        listOf("stop", "resume", "discard").forEach { action ->
            TextButton(onClick = {
                scope.launch {
                    val result = withContext(Dispatchers.IO) { runCatching { api.workerAction(chatId, worker, action) } }
                    result.onFailure { onError(it.message) }
                }
            }) { Text(action) }
        }
    }
}

@Composable
internal fun PasswordChange(api: LaylaApi) {
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
internal fun fieldColors() = OutlinedTextFieldDefaults.colors(
    focusedTextColor = Color.White,
    unfocusedTextColor = Soft,
    cursorColor = Blue,
    focusedBorderColor = Blue,
    unfocusedBorderColor = Line,
    focusedContainerColor = Raised,
    unfocusedContainerColor = Raised,
    focusedLabelColor = Color(0xFF99C9FF),
    unfocusedLabelColor = Muted,
    focusedPlaceholderColor = Muted,
    unfocusedPlaceholderColor = Muted,
)

@Composable
internal fun Field(label: String, value: String, password: Boolean = false, onChange: (String) -> Unit) {
    OutlinedTextField(
        value = value,
        onValueChange = onChange,
        modifier = Modifier.fillMaxWidth(),
        label = { Text(label) },
        singleLine = label != "Приватный ключ" && label != "Содержимое" && label != "Текст" && label != "Инструкции" && label != "Заметки" && label != "Ответ",
        visualTransformation = if (password) PasswordVisualTransformation() else androidx.compose.ui.text.input.VisualTransformation.None,
        keyboardOptions = if (label == "Порт") KeyboardOptions(keyboardType = KeyboardType.Number) else KeyboardOptions.Default,
        shape = RoundedCornerShape(12.dp),
        colors = fieldColors(),
    )
}
