package demo;

import org.junit.jupiter.api.Test;

public class JsonFileImportMigrationTest extends AbstractMigrationTest {

    @Test
    public void migrate() {
        testMigrationTo2_0_0();
        testMigrationTo2_1_0();
    }
}
