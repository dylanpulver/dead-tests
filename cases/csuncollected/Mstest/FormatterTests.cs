using Microsoft.VisualStudio.TestTools.UnitTesting;

namespace Fixture.MstestSuite
{
    [TestClass]
    public class FormatterTests
    {
        [TestMethod]
        public void FormatsInteger()
        {
            Assert.AreEqual("12", 12.ToString());
        }

        // No [TestMethod]: MSTest will not collect this.
        public void FormatsNegative()
        {
            Assert.AreEqual("-12", (-12).ToString());
        }

        // Nested, private, and handed to the adapter as data rather than run.
        // testfx's UnitTestRunnerTests is full of these, and MSTest reports no
        // diagnostic: a private class is simply never collected.
        private class DummyTestClass
        {
            [TestMethod]
            public void RealOne()
            {
                Assert.IsTrue(true);
            }

            public void TestMethodToTestInProgress()
            {
                Assert.IsTrue(false);
            }
        }
    }
}
