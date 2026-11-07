# Fixture expectations, written BEFORE running the scanner

Guards `bin/find-uncollected-php-tests.py`. PHPUnit collects a method only when its name
starts with `test`, or it carries `@test` / `#[Test]`. A method that asserts but cannot be
collected is silently dead.

Expected hits: exactly 1
  1. tests/ShapesTest.php :: getGetForeignRelationKey()   a `get` typo for `test`, asserts,
                                                          called from nowhere. This is the real
                                                          silverstripe shape (PolymorphicHasManyListTest).

Expected NON-hits:
  2. tests/ShapesTest.php :: testNormal()          collected, has the prefix
  3. tests/ShapesTest.php :: isCollectedViaAnnotation()   has @test
  4. tests/ShapesTest.php :: isCollectedViaAttribute()    has #[Test]
  5. tests/ShapesTest.php :: disabled_parkedOnPurpose()   parked by prefix, deliberate
  6. tests/ShapesTest.php :: sharedHelper()        called by testNormal, so it is a helper
  7. src/Dev/FunctionalTest.php :: assertThingBySelector()
       A `*Test.php` SUFFIX on a file in `src/` is a production base class, not a test file.
       silverstripe ships exactly this and it produced two false positives on 2026-10-31.
       The file must sit under a `test`/`tests` DIRECTORY to be examined at all.
