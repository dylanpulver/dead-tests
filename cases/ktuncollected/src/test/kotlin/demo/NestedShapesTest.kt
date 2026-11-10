package demo

import org.junit.jupiter.api.Nested
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.Assertions.assertTrue

class NestedShapesTest {
    @Nested
    inner class WhenEmpty {
        @Test
        fun testCounted() {
            assertTrue(true)
        }

        fun testForgottenInNested() {
            assertTrue(false)
        }
    }

    inner class Fixture {
        fun testData() {
            println("not a nested test class")
        }
    }
}
