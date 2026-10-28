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
}
