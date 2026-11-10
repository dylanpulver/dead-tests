package demo

import org.junit.jupiter.api.Test

class SubclassTest : AbstractBaseTest() {
    @Test
    fun driver() {
        testTemplateStep()
        listOf(1).forEach { _ -> println(::testReferenced) }
    }

    fun testReferenced() {
        println("passed by reference")
    }
}
