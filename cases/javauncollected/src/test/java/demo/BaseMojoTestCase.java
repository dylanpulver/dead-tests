package demo;

import junit.framework.TestCase;

// Stands in for Maven's AbstractMojoTestCase. The chain that matters is
// MojoStyleTest -> BaseMojoTestCase -> TestCase, resolved transitively.
public abstract class BaseMojoTestCase extends TestCase {
}
