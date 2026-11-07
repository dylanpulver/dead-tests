package demo;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertTrue;

// keycloak's shape: an abstract base holding template methods that only
// subclasses call, from other files.
public abstract class AbstractMigrationTest {

    protected void testMigrationTo2_0_0() {
        assertTrue(true);
    }

    protected void testMigrationTo2_1_0() {
        assertTrue(true);
    }
}
