package demo;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertTrue;

public class DisabledShapesTest {

    @Test
    public void testLiveOne() {
        assertTrue(true);
    }

    // dubbo's EnableDubboConfigTest shape: the annotation crossed out.
    // @Test
    public void testCrossedOutAnnotation() {
        assertTrue(true);
    }

    /*@Test
    public void testWholeMethodCommentedOut() throws Exception {
        assertTrue(true);
    }
    */
}
