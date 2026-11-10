package demo

import io.kotest.core.spec.style.StringSpec
import org.junit.jupiter.api.Test

class KotestStyleTest : StringSpec({
    "runs without an annotation" { }
}) {
    fun testNotJUnit() {
        println("kotest file")
    }
}
