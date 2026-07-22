import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestDatabase(unittest.TestCase):
    def test_schema_file_exists(self):
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "database", "schema.sql")))

    def test_db_module_exists(self):
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "database", "db.py")))

    def test_migrate_script_exists(self):
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "database", "migrate.py")))

    def test_schema_has_reviews_table(self):
        with open(os.path.join(ROOT, "database", "schema.sql")) as f:
            sql = f.read()
        self.assertIn("CREATE TABLE IF NOT EXISTS reviews", sql)

    def test_schema_has_themes_table(self):
        with open(os.path.join(ROOT, "database", "schema.sql")) as f:
            sql = f.read()
        self.assertIn("CREATE TABLE IF NOT EXISTS themes", sql)

    def test_schema_has_insights_table(self):
        with open(os.path.join(ROOT, "database", "schema.sql")) as f:
            sql = f.read()
        self.assertIn("CREATE TABLE IF NOT EXISTS insights", sql)

    def test_schema_has_categories_table(self):
        with open(os.path.join(ROOT, "database", "schema.sql")) as f:
            sql = f.read()
        self.assertIn("CREATE TABLE IF NOT EXISTS categories", sql)

    def test_schema_has_sentiment_table(self):
        with open(os.path.join(ROOT, "database", "schema.sql")) as f:
            sql = f.read()
        self.assertIn("CREATE TABLE IF NOT EXISTS sentiment", sql)

    def test_schema_has_research_table(self):
        with open(os.path.join(ROOT, "database", "schema.sql")) as f:
            sql = f.read()
        self.assertIn("CREATE TABLE IF NOT EXISTS research_data", sql)

    def test_schema_uses_jsonb_array(self):
        with open(os.path.join(ROOT, "database", "schema.sql")) as f:
            sql = f.read()
        self.assertIn("TEXT[]", sql)

    def test_schema_has_indexes(self):
        with open(os.path.join(ROOT, "database", "schema.sql")) as f:
            sql = f.read()
        self.assertIn("CREATE INDEX", sql)

    def test_db_module_has_get_connection(self):
        with open(os.path.join(ROOT, "database", "db.py")) as f:
            code = f.read()
        self.assertIn("def get_connection", code)

    def test_db_module_has_query(self):
        with open(os.path.join(ROOT, "database", "db.py")) as f:
            code = f.read()
        self.assertIn("def query", code)

    def test_db_module_has_execute(self):
        with open(os.path.join(ROOT, "database", "db.py")) as f:
            code = f.read()
        self.assertIn("def execute", code)

    def test_migrate_has_run_migration(self):
        with open(os.path.join(ROOT, "database", "migrate.py")) as f:
            code = f.read()
        self.assertIn("def run_migration", code)

    def test_migrate_loads_all_json_files(self):
        with open(os.path.join(ROOT, "database", "migrate.py")) as f:
            code = f.read()
        self.assertIn("ai_insights.json", code)
        self.assertIn("live_scraped_data.json", code)
        self.assertIn("cleaned_feedback.json", code)

    def test_requirements_exists(self):
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "requirements.txt")))

    def test_requirements_has_psycopg2(self):
        with open(os.path.join(ROOT, "requirements.txt")) as f:
            reqs = f.read()
        self.assertIn("psycopg2", reqs)


if __name__ == "__main__":
    unittest.main()
