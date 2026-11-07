//
// Copyright (C) 2010 Novell Inc. http://novell.com
//
// uno's shape: a vendored Mono test suite sitting at a path with no vendor
// marker in it. Must still be REPORTED, and TAGGED so the header gets read.
//
using NUnit.Framework;

namespace Fixture.NunitSuite
{
    [TestFixture]
    public class VendoredLookalikeTests
    {
        [Test]
        public void CollectedOne()
        {
            Assert.That(1, Is.EqualTo(1));
        }

        public void StartMemberWriteEndObject()
        {
            Assert.That(2, Is.EqualTo(2));
        }
    }
}
