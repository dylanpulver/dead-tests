package demo

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test
import kotlinx.coroutines.test.runTest

class DeadTest {
    @Test fun testRealOne() {
        testLocalHelper()
        assertEquals(2, 1 + 1)
    }

    @Test
    fun `real backticked test`() {
        assertEquals(4, 2 + 2)
    }

    fun testNothingRunsThis() {
        assertEquals(3, 1 + 1)
    }

    fun `forgotten backticked test`() {
        assertEquals("a", "b")
    }

    fun testForgottenCoroutine() = runTest {
        assertEquals(1, 2)
    }

    fun testLocalHelper() {
        println("helper")
    }

    private fun testPrivateHelper() {
        println("private")
    }

    fun testValue(): Int = 3

    fun testWithArg(x: Int) {
        assertEquals(x, x)
    }

    // @Test
    fun testParkedOnPurpose() {
        assertEquals(1, 2)
    }

    /*
    fun testCommentedOut() {
        assertEquals(1, 2)
    }
    */

    val fixture = """
        fun testInsideRawString() {
            "quoted" inside
        }
    """

    companion object {
        fun testFromCompanion() {
            println("static")
        }
    }
}
