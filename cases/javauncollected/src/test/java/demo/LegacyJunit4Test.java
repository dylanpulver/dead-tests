package demo;

import org.junit.Test;
import static org.junit.Assert.assertEquals;

// keycloak's shape: a JUnit 4 class. JUnit 4 requires @Test exactly as 5 does,
// so the seam is identical and must be reported here too.
public class LegacyJunit4Test {

    @Test
    public void testAnnotated() {
        assertEquals(1, 1);
    }

    public void testForgottenHere() {
        assertEquals(2, 2);
    }
}
