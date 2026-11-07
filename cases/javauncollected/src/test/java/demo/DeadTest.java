package demo;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;

public class DeadTest {

    @Test
    public void testRealOne() {
        testLocalHelper(2);
    }

    // Called by testRealOne in this same file: a helper, not a dead test.
    public void testLocalHelper(int n) {
        assertEquals(n, n);
    }

    // Nothing anywhere calls this, and it carries no annotation.
    public void testNothingRunsThis() {
        assertEquals(1, 1);
    }
}
