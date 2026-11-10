package demo

import org.junit.Assert.assertEquals
import org.junit.Test

class LegacyJunit4Test {
    @Test
    fun testRuns() {
        assertEquals(1, 1)
    }

    fun testForgottenHere() {
        assertEquals(1, 2)
    }
}
