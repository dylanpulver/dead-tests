<?php
class ShapesTest extends \PHPUnit\Framework\TestCase
{
    public function testNormal(): void
    {
        $this->assertSame(1, $this->sharedHelper());
    }

    // HIT: `get` typed where `test` was meant. Asserts, called from nowhere.
    public function getGetForeignRelationKey(): void
    {
        $this->assertSame('FavouriteRelation', $this->subject->getForeignRelationKey());
    }

    /**
     * @test
     */
    public function isCollectedViaAnnotation(): void
    {
        $this->assertTrue(true);
    }

    #[\PHPUnit\Framework\Attributes\Test]
    public function isCollectedViaAttribute(): void
    {
        $this->assertTrue(true);
    }

    public function disabled_parkedOnPurpose(): void
    {
        $this->assertTrue(false);
    }

    // Parked by typing `no` in front of `test`, as yii2 does for a generator.
    public function notestGenerateVectors(): void
    {
        $this->assertSame('vectors', $this->subject->generate());
    }

    private function sharedHelper(): int
    {
        $this->assertNotNull($this->subject);
        return 1;
    }
}
