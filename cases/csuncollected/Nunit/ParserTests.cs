using NUnit.Framework;

namespace Fixture.NunitSuite
{
    [TestFixture]
    public class ParserTests
    {
        [Test]
        public void ParsesDigits()
        {
            Assert.That(int.Parse("12"), Is.EqualTo(12));
        }

        [TestCase(" ")]
        [TestCase("\t")]
        public void ParsesWhitespace(string input)
        {
            Assert.That(input.Trim(), Is.Empty);
        }

        // No [Test]: NUnit will not collect this.
        public void ParsesEmptyInput()
        {
            Assert.That(string.Empty, Is.Empty);
        }

        // Deliberately disabled, apache/avro's shape: the attribute is crossed
        // out and a ticket says why. All three avro findings read like this.
        // AVRO-625 [Test]
        // SocketTransceiver does not permit out-of-order requests.
        public void ParsesOutOfOrder()
        {
            Assert.That("ba", Is.EqualTo("ab"));
        }

        // nhibernate's shape: the attribute comes FIRST and the reason follows.
        //[Test] not required
        public void ParsesRedundantly()
        {
            Assert.That("a", Is.EqualTo("a"));
        }

        /* SharpZipLib's shape: a prose block with no attribute in sight that
         * explains why the test is off and ends with a decision.
         * The FileShare value is not meant for cross-process locking, so this
         * cannot be tested without a second process.
         * Therefore I would remove this test.
         **/
        public void ParsesAcrossProcesses()
        {
            Assert.That("x", Is.EqualTo("y"));
        }
    }
}
