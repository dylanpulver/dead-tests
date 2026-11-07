package demo;

// openapi-generator's shape: a JUnit 3 class that statically imports a JUnit 5
// ASSERTION helper. The import proves nothing about how tests are collected.
import static org.junit.jupiter.api.Assertions.assertNotEquals;

public class MojoStyleTest extends BaseMojoTestCase {

    // Collected BY NAME, JUnit 3 style. Not a finding.
    public void testCollectedByName() throws Exception {
        assertNotEquals(1, 2);
    }
}
