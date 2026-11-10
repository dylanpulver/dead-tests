package demo

import org.junit.jupiter.api.Test

abstract class AbstractBaseTest {
    protected fun testTemplateStep() {
        println("called by subclasses")
    }

    @Test
    fun testShared() {
        println("ok")
    }
}
