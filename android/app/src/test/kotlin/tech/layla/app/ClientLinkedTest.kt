package tech.layla.app

import org.junit.Assert.assertEquals
import org.junit.Test
import tech.layla.client.Catalog
import tech.layla.client.SessionJar

class ClientLinkedTest {
    @Test fun appUsesTheWebSessionAndAllDomains() {
        assertEquals("layla_session", SessionJar.COOKIE)
        assertEquals(5, Catalog.domains.size)
        assertEquals(15, Catalog.settings.size)
    }
}
