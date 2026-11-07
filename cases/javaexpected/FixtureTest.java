import org.junit.Test;
import static org.junit.Assert.*;

public class FixtureTest {

    @Test(expected = IllegalArgumentException.class)
    public void deadTailSimple() {
        parse("nope");
        assertEquals(1, parse("ok"));
    }

    @Test(expected = IllegalStateException.class)
    public void deadTailAfterBlock() {
        setUp();
        if (flag) {
            mutate();
        }
        boom();
        assertTrue(after());
    }

    @Test(expected = Exception.class)
    public void deadTailExceptionClass() {
        boom();
        assertNotNull(value());
    }

    @Test(expected = AssertionError.class)
    public void raiserIsTheAssertion() {
        setUp();
        assertTrue(false);
    }

    @Test(expected = Throwable.class)
    public void expectedThrowable() {
        boom();
        assertTrue(after());
    }

    @Test(expected = Error.class)
    public void expectedError() {
        boom();
        assertTrue(after());
    }

    @Test
    public void plainTest() {
        doThing();
        assertEquals(1, value());
    }

    @Test(expected = IllegalArgumentException.class)
    public void assertNotLast() {
        boom();
        assertTrue(after());
        cleanup();
    }

    @Test(expected = AssertionError.class)
    public void singleStatementAssert() {
        assertTrue(false);
    }

    @Test(expected = IllegalArgumentException.class)
    public void noTrailingAssertion() {
        setUp();
        boom();
    }

    @Test
    public void junit5AssertThrows() {
        assertThrows(IllegalArgumentException.class, () -> boom());
    }
}
