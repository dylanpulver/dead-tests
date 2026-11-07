<?php
namespace App\Dev;

/**
 * A production base class that ships assertion helpers for users' tests.
 * Not a test file, despite the Test.php suffix.
 */
abstract class FunctionalTest extends \PHPUnit\Framework\TestCase
{
    public function assertThingBySelector($selector, $expected): void
    {
        $this->assertSame($expected, $this->cssParser()->getBySelector($selector));
    }
}
