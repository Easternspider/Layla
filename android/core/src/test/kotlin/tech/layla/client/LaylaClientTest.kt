package tech.layla.client

import okhttp3.mockwebserver.Dispatcher
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.RecordedRequest
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CatalogTest {
    @Test fun sameDomainsAndSettingsAsWeb() {
        assertEquals(listOf("code", "pentest", "osint", "design", "agent"), Catalog.domains.map { it.slug })
        assertEquals(15, Catalog.settings.size)
        assertEquals("Пользователи", Catalog.settings.first { it.slug == "users" }.label)
        assertTrue(Catalog.settings.first { it.slug == "users" }.adminOnly)
        val ids = Catalog.sections.map { it.id }.toSet()
        assertTrue("code-chat" in ids && "agent-servers" in ids && "settings-trash" in ids)
        assertEquals("/api/chats?domain=agent", Catalog.section("agent-tasks").path)
        assertEquals("server", Catalog.section("agent-servers").form)
        assertEquals("intel", Catalog.section("osint-sources").open)
        assertEquals("provider", Catalog.section("settings-providers").form)
        assertTrue(Catalog.sectionsOf("pentest").size == 6)
    }
}

class SessionTest {
    @Test fun cookieSurvivesRestart() {
        val store = MemoryStore()
        val server = MockWebServer()
        server.enqueue(MockResponse().setBody("""{"id":"u1","email":"a@b.c","is_admin":true}""")
            .addHeader("Set-Cookie", "layla_session=token-1; Path=/; HttpOnly"))
        server.start()
        try {
            val api = LaylaApi(SessionJar(store), server.url("/").toString().trimEnd('/'))
            val user = api.login("A@B.c", "secret")
            assertEquals("a@b.c", user.getString("email"))
            assertEquals("token-1", api.jar.sessionToken())
            val again = LaylaApi(SessionJar(store), api.base)
            assertEquals("token-1", again.jar.sessionToken())
        } finally {
            server.shutdown()
        }
    }
}

class ApiTest {
    @Test fun loginUsesTheSameAccountAndSendsTheSession() {
        val seen = mutableListOf<RecordedRequest>()
        val server = MockWebServer()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                seen.add(request)
                return when (request.path) {
                    "/api/auth/login" -> MockResponse()
                        .setBody("""{"id":"u1","email":"owner@layla.local","is_admin":false}""")
                        .addHeader("Set-Cookie", "layla_session=same-as-web; Path=/; HttpOnly")
                    "/api/auth/me" -> {
                        if (request.getHeader("Cookie")?.contains("layla_session=same-as-web") != true) {
                            MockResponse().setResponseCode(401).setBody("""{"detail":"Требуется аутентификация"}""")
                        } else MockResponse().setBody("""{"id":"u1","email":"owner@layla.local"}""")
                    }
                    "/api/servers" -> {
                        assertTrue(request.body.readUtf8().contains("\"auth\":\"password\""))
                        MockResponse().setResponseCode(201).setBody("""{"id":"s1","host":"10.0.0.5","user":"root","auth":"password"}""")
                    }
                    else -> MockResponse().setResponseCode(404)
                }
            }
        }
        server.start()
        try {
            val api = LaylaApi(SessionJar(), server.url("/").toString().trimEnd('/'))
            api.login("owner@layla.local", "pw")
            assertEquals("owner@layla.local", api.me().getString("email"))
            val serverRow = api.addServer("10.0.0.5", 22, "root", "password", "secret")
            assertEquals("password", serverRow.getString("auth"))
            assertEquals("/api/auth/login", seen[0].path)
            assertTrue(seen[0].body.readUtf8().contains("owner@layla.local"))
        } finally {
            server.shutdown()
        }
    }

    @Test fun rejectedLoginDoesNotInventASession() {
        val server = MockWebServer()
        server.enqueue(MockResponse().setResponseCode(401).setBody("""{"detail":"Неверная почта или пароль"}"""))
        server.start()
        try {
            val api = LaylaApi(SessionJar(), server.url("/").toString().trimEnd('/'))
            val error = runCatching { api.login("a@b.c", "nope") }.exceptionOrNull()
            assertTrue(error is LaylaException)
            assertEquals(401, (error as LaylaException).status)
            assertEquals("Неверная почта или пароль", error.message)
            assertTrue(api.jar.sessionToken().isNullOrBlank())
        } finally {
            server.shutdown()
        }
    }

    @Test fun labelPrefersPersonAtHost() {
        val row = JSONObject().put("user", "root").put("host", "latvia.example").put("id", "1")
        assertEquals("root@latvia.example", labelOf(row))
        assertFalse(labelOf(JSONObject().put("title", "Задача")).isBlank())
    }

    @Test fun sameRoutesAsTheWebClient() {
        val hits = mutableListOf<String>()
        val bodies = mutableListOf<String>()
        val server = MockWebServer()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                hits.add("${request.method} ${request.path}")
                bodies.add(request.body.readUtf8())
                return MockResponse().setBody("""{"id":"1","content_sha256":"abc","files":[],"sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}""")
            }
        }
        server.start()
        try {
            val api = LaylaApi(SessionJar(), server.url("/").toString().trimEnd('/'))
            api.setScope("e1", listOf("10.0.0.5"), emptyList())
            api.confirmScope("e1")
            api.setVenue("e1", "attack_box", "direct")
            api.setOffensive("e1", true)
            api.addFinding("e1", "xss", "high", "reflected")
            api.generateReport("e1")
            api.startAgent("e1", "проверь scope", "interactive")
            api.stopAgent("r1")
            api.approveStep("s1")
            api.writeFile("p1", "src/App.kt", "fun main(){}", null)
            api.readFile("p1", "src/App.kt")
            api.gitCommit("p1", "save")
            api.gitPush("p1")
            api.importRepo("https://example.com/repo.git", "repo")
            api.createChat("code", "задача", "p1", null)
            api.renameChat("c1", "новое")
            api.deleteChat("c1")
            api.compactChat("c1")
            api.rollback("c1", "m1")
            api.workerAction("c1", "w1", "discard")
            api.answerCode("c1", "q1", "да")
            api.runLookup("case", "shodan", "example.com")
            api.addArtifact("case", "заметка", "текст", "https://example.com/src")
            api.createDesign("Layla", "тёмная", "react")
            api.createProvider("OpenAI", "openai_compatible", "https://api.openai.com/v1", "sk-test")
            api.addKey("pr1", "sk-test", "основной")
            api.createPersona("Ревьюер", "смотри diff")
            api.addKnowledge("заметка", "текст", "code")
            api.searchKnowledge("текст")
            api.createCombo("ночная", listOf("gpt"))
            api.saveTelegram("123:abc", "1", "https://layla.example")
            api.saveIntelKey("shodan", "key")
            api.installLanguage("python", "3.12")
            api.removeLanguage("python", "3.12")
            api.saveAgentConfig(
                JSONObject().put("preset", "pulse").put("role_models", JSONObject().put("explorer", "gpt")),
                "constellation",
            )
            api.updateUser("u2", admin = false, active = true, reset = true)
            api.restoreChat("c9")
            api.purgeChat("c9")
            api.emptyTrash()
        } finally {
            server.shutdown()
        }
        assertTrue(hits.contains("PUT /api/engagements/e1/scope"))
        assertTrue(hits.contains("POST /api/engagements/e1/scope/confirm"))
        assertTrue(hits.contains("PUT /api/engagements/e1/venue"))
        assertTrue(hits.contains("POST /api/engagements/e1/agent/runs"))
        assertTrue(hits.contains("POST /api/agent/runs/r1/stop"))
        assertTrue(hits.contains("POST /api/agent/steps/s1/approve"))
        assertTrue(hits.contains("GET /api/projects/p1/file?path=src%2FApp.kt"))
        assertTrue(hits.contains("POST /api/projects/p1/git/commit"))
        assertTrue(hits.contains("POST /api/projects/import"))
        assertTrue(hits.contains("POST /api/chats/c1/workers/w1/discard?discard_changes=true"))
        assertTrue(hits.contains("POST /api/osint/cases/case/lookups"))
        assertTrue(hits.contains("POST /api/designs/generate"))
        assertTrue(hits.contains("PUT /api/integrations/intelligence/shodan"))
        assertTrue(hits.contains("DELETE /api/sandbox/languages"))
        assertTrue(hits.contains("DELETE /api/trash"))
        val scope = bodies.first { it.contains("10.0.0.5") }
        assertTrue(scope.contains("\"allow\""))
        val file = bodies.first { it.contains("src/App.kt") }
        assertTrue(file.contains("\"expected_sha256\":null"))
        val config = bodies.first { it.contains("constellation") }
        assertTrue(config.contains("\"explorer\":\"gpt\""))
        val design = bodies.first { it.contains("\"stack\":\"react\"") }
        assertTrue(design.contains("тёмная"))
        val user = bodies.first { it.contains("reset_password") }
        assertTrue(user.contains("\"is_admin\":false"))
    }
}
