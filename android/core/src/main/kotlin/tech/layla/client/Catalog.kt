package tech.layla.client

/** Те же разделы, что у веб-клиента. Имена и slug не расходятся с frontend/src/lib. */
data class Domain(
    val slug: String,
    val label: String,
    val tagline: String,
    val tabs: List<String>,
)

data class Setting(val slug: String, val label: String, val blurb: String, val adminOnly: Boolean = false)

data class Section(
    val id: String,
    val group: String,
    val title: String,
    val path: String,
    val arrayKey: String? = null,
    val form: String? = null,
    val open: String? = null,
)

object Catalog {
    val domains = listOf(
        Domain("code", "Код", "Чат-агент с доступом к файлам проекта и репозиториям.", listOf("Чат", "Файлы", "Репозитории")),
        Domain("pentest", "Пентест", "Авторизованные engagement'ы: scope, находки, отчёты, агент.", listOf("Обзор", "Находки", "Отчёты", "Серверы", "Активность", "Агент")),
        Domain("osint", "OSINT", "Кейсы разведки по открытым источникам через intelligence-API.", listOf("Кейсы", "Таймлайн", "Источники")),
        Domain("design", "Дизайн", "Генерация UI-артефактов по брифу.", listOf("Бриф", "Превью", "Код", "Дизайн-система")),
        Domain("agent", "Агент", "Задачи по своим серверам: состояние, установка, файлы и поиск.", listOf("Задачи", "Серверы")),
    )

    val settings = listOf(
        Setting("general", "Общие", "Учётная запись и пароль."),
        Setting("users", "Пользователи", "Учётные записи, роли, сброс паролей.", adminOnly = true),
        Setting("appearance", "Внешний вид", "Тёмная тема, как в вебе."),
        Setting("providers", "Провайдеры", "Профили подключения LLM."),
        Setting("agent", "Агент", "Конфигурация оркестрации."),
        Setting("personas", "Роли", "Промты ролей и доступ к файлам."),
        Setting("sandbox", "Песочница", "Запуск кода и языки."),
        Setting("knowledge", "База знаний", "Документы RAG."),
        Setting("security", "Безопасность", "Аудит-лог своих действий."),
        Setting("integrations", "Интеграции", "MCP, Telegram, intelligence-API."),
        Setting("local-api", "Локальный API", "Служба и метаданные этого сервера."),
        Setting("data", "Данные", "Корзина и восстановление."),
        Setting("accounts-lab", "Accounts Lab", "Здоровье аккаунтов и combos."),
        Setting("privacy-chain", "Privacy Chain", "Egress задаётся у engagement."),
        Setting("trash", "Корзина", "Удалённые чаты и проекты."),
    )

    val sections = listOf(
        Section("code-chat", "code", "Чат", "/api/chats?domain=code", form = "chat", open = "chat"),
        Section("code-files", "code", "Файлы", "/api/projects", form = "project", open = "project"),
        Section("code-repos", "code", "Репозитории", "/api/projects", form = "import", open = "project"),
        Section("pentest-overview", "pentest", "Обзор", "/api/engagements", form = "engagement", open = "engagement"),
        Section("pentest-findings", "pentest", "Находки", "/api/engagements", open = "engagement"),
        Section("pentest-reports", "pentest", "Отчёты", "/api/engagements", open = "engagement"),
        Section("pentest-servers", "pentest", "Серверы", "/api/servers", form = "server", open = "server"),
        Section("pentest-activity", "pentest", "Активность", "/api/engagements/board", open = "engagement"),
        Section("pentest-agent", "pentest", "Агент", "/api/chats?domain=pentest", form = "chat", open = "chat"),
        Section("osint-cases", "osint", "Кейсы", "/api/osint/cases", form = "case", open = "case"),
        Section("osint-timeline", "osint", "Таймлайн", "/api/osint/cases", open = "case"),
        Section("osint-sources", "osint", "Источники", "/api/integrations/intelligence", open = "intel"),
        Section("design-brief", "design", "Бриф", "/api/designs", form = "design", open = "design"),
        Section("design-preview", "design", "Превью", "/api/designs", open = "design"),
        Section("design-code", "design", "Код", "/api/designs", open = "design"),
        Section("design-system", "design", "Дизайн-система", "/api/designs", open = "design"),
        Section("agent-tasks", "agent", "Задачи", "/api/chats?domain=agent", form = "chat", open = "chat"),
        Section("agent-servers", "agent", "Серверы", "/api/servers", form = "server", open = "server"),
        Section("settings-general", "settings", "Общие", "/api/auth/me", open = "account"),
        Section("settings-users", "settings", "Пользователи", "/api/admin/users", form = "user", open = "user"),
        Section("settings-appearance", "settings", "Внешний вид", "/api/auth/me"),
        Section("settings-providers", "settings", "Провайдеры", "/api/providers", form = "provider", open = "provider"),
        Section("settings-agent", "settings", "Агент", "/api/agent/config", open = "agent-config"),
        Section("settings-personas", "settings", "Роли", "/api/personas", form = "persona", open = "persona"),
        Section("settings-sandbox", "settings", "Песочница", "/api/sandbox/status", open = "sandbox"),
        Section("settings-knowledge", "settings", "База знаний", "/api/knowledge", form = "knowledge", open = "knowledge"),
        Section("settings-security", "settings", "Безопасность", "/api/audit", open = "audit"),
        Section("settings-integrations", "settings", "Интеграции", "/api/mcp/servers", form = "mcp", open = "mcp"),
        Section("settings-telegram", "settings", "Telegram", "/api/integrations/telegram", open = "telegram"),
        Section("settings-local-api", "settings", "Локальный API", "/api/meta", open = "meta"),
        Section("settings-data", "settings", "Данные", "/api/trash", arrayKey = "chats"),
        Section("settings-accounts-lab", "settings", "Accounts Lab", "/api/providers/accounts/health", open = "health"),
        Section("settings-combos", "settings", "Combos", "/api/combos", form = "combo", open = "combo"),
        Section("settings-privacy-chain", "settings", "Privacy Chain", "/api/engagements"),
        Section("settings-trash", "settings", "Корзина", "/api/trash", arrayKey = "chats", open = "trash-chat"),
        Section("settings-trash-projects", "settings", "Корзина проектов", "/api/trash", arrayKey = "projects", open = "trash-project"),
        Section("settings-jobs", "settings", "Задачи", "/api/jobs?limit=100", open = "job"),
        Section("settings-models", "settings", "Модели", "/api/models"),
    )

    fun domain(slug: String) = domains.first { it.slug == slug }

    fun sectionsOf(group: String) = sections.filter { it.group == group }

    fun section(id: String) = sections.first { it.id == id }
}
