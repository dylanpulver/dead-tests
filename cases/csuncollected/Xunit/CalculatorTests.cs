using System;
using Xunit;

namespace Fixture.XunitSuite
{
    public class CalculatorTests : IDisposable
    {
        [Fact]
        public void AddsTwoPositives()
        {
            AssertBothOrders(2, 3, 5);
        }

        [Theory]
        [InlineData(2, 3, 6)]
        [InlineData(4, 5, 20)]
        public void MultipliesPairs(int a, int b, int expected)
        {
            Assert.Equal(expected, a * b);
        }

        [Fact(Skip = "Pending the overflow rewrite")]
        public void SkippedOnPurpose()
        {
            Assert.True(false);
        }

        [Fact]
        public void RoundTripsText()
        {
            AssertRoundTrip("hello");
        }

        // No attribute, nothing calls it: this runs nowhere.
        public void AddsTwoNegatives()
        {
            Assert.Equal(-5, -2 + -3);
            Assert.Equal(-5, -3 + -2);
            Assert.True(-2 + -3 < 0);
        }

        private void AssertBothOrders(int a, int b, int expected)
        {
            Assert.Equal(expected, a + b);
            Assert.Equal(expected, b + a);
        }

        public void AssertRoundTrip(string value)
        {
            Assert.Equal(value, new string(value.ToCharArray()));
        }

        public void Dispose()
        {
            Assert.True(true);
        }
    }
}
