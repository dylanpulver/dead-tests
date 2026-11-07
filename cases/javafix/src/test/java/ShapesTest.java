import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.BeforeEach;

public class ShapesTest {

    @BeforeEach
    public void setUp() {
        // hook, not a hit
    }

    @Test
    public void testPlainAnnotated() {
        assertTrue(true);
    }

    // kafka shape 1: multi-line annotation with parenthesised args
    @ClusterTest(
        brokerSecurityProtocol = SecurityProtocol.SASL_PLAINTEXT
    )
    public void testMultiLineParens() {
        assertTrue(true);
    }

    // kafka shape 2: nested annotations with BRACES in the argument list
    @ClusterTests({
        @ClusterTest(serverProperties = {
            @ClusterConfigProperty(key = "a", value = "0")
        }),
        @ClusterTest(serverProperties = {
            @ClusterConfigProperty(key = "a", value = "1000")
        })
    })
    public void testNestedBraces() {
        assertTrue(true);
    }

    // TRUE POSITIVE: looks like a test, no annotation anywhere above it
    public void testGenuinelyUnannotated() {
        assertTrue(true);
    }

    // not a hit: a helper, no test prefix
    private void helper() {
        assertTrue(true);
    }
}
