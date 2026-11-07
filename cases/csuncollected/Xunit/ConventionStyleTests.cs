using Xunit;

namespace Fixture.XunitSuite
{
    // Stand-in for TestFramework.ForTestingMSTest.TestContainer, which
    // microsoft/testfx uses to test MSTest without bootstrapping MSTest: every
    // public method is a test by convention, so no attribute is missing.
    public abstract class TestContainer
    {
    }

    public sealed class ConventionStyleTests : TestContainer
    {
        public void ChecksSomethingByConvention()
        {
            Assert.Equal(4, 2 + 2);
        }

        public void ChecksSomethingElseByConvention()
        {
            Assert.True(1 < 2);
        }
    }
}
