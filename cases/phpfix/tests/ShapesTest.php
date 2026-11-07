<?php
class ShapesTest extends \PHPUnit\Framework\TestCase
{
    // TRUE POSITIVE: a throwing call sits between expectException and the
    // assertion, so the assertion is dead.
    public function testDeadAfterThrowingCall(): void
    {
        $this->expectException(\RuntimeException::class);
        $this->subject->explode();
        self::assertSame('never reached', $this->subject->value());
    }

    // NOT a hit: the assertion IS the raiser, nothing between it and
    // expectException. This is how EasyAdminBundle tests its own assertion
    // helpers.
    public function testAssertionIsTheRaiser(): void
    {
        $this->expectException(\PHPUnit\Framework\AssertionFailedError::class);
        self::assertIndexFullEntityCount(-1);
    }

    // NOT a hit: setup before expectException does not count as the thrower.
    public function testSetupThenRaisingAssertion(): void
    {
        $categories = CategoryFactory::createMany(3);
        $this->client->request('GET', $this->generateIndexUrl());
        $this->expectException(\PHPUnit\Framework\AssertionFailedError::class);
        self::assertIndexFullEntityCount(\count($categories) + 1);
    }
}
