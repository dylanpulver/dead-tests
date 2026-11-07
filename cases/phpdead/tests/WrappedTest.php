<?php
class WrappedTest extends TestCase
{
    public function testSingleLineDead(): void
    {
        $this->expectException(RuntimeException::class);

        $tester = $this->getTester();
        self::assertEquals(1, $tester->run(['a' => 'b']));
    }

    public function testWrappedDead(): void
    {
        $this->expectException(RuntimeException::class);

        $tester = $this->getTester();
        self::assertEquals(
            1,
            $tester->run(
                ['a' => 'b']
            )
        );
    }

    public function testThrowerLastIsFine(): void
    {
        $this->expectException(RuntimeException::class);

        $tester = $this->getTester();
        $tester->run(['a' => 'b']);
    }

    public function testMultiLineExpectMessageThenDeadAssert(): void
    {
        $this->expectException(RuntimeException::class);
        $this->expectExceptionMessage(
            "Given class does not implement Foo: Bar\n".
            "Behavior can be unpredictable (in particular if you unserialize)\n".
            "But if you are sure, use allow(static fn () => ...)",
        );

        $p = make();
        $p2 = allow(static fn () => thing($p));

        $this->assertSame([], $p2->getFilters());
    }
}
