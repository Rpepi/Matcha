import pytest
from unittest.mock import MagicMock, patch, call
from pathlib import Path


def make_mock_conn(already_done: set[str] = frozenset()):
    """Build a psycopg connection mock with configurable migration history."""
    conn = MagicMock()

    def execute_side_effect(sql, params=None):
        cursor = MagicMock()
        sql_stripped = sql.strip()
        if "SELECT filename FROM migrations" in sql_stripped:
            cursor.fetchall.return_value = [(f,) for f in already_done]
        else:
            cursor.fetchall.return_value = []
        return cursor

    conn.execute.side_effect = execute_side_effect
    conn.commit = MagicMock()
    conn.close = MagicMock()
    return conn


class TestMigrationRunner:
    def test_creates_migrations_table(self):
        from app.db.migrations.runner import run_migration
        conn = make_mock_conn()

        with patch("psycopg.connect", return_value=conn), \
             patch("os.listdir", return_value=[]), \
             patch.dict("os.environ", {"DATABASE_URL": "postgresql://test"}):
            run_migration()

        create_calls = [
            str(c) for c in conn.execute.call_args_list
            if "CREATE TABLE IF NOT EXISTS migrations" in str(c)
        ]
        assert len(create_calls) == 1

    def test_applies_new_migration_files(self, tmp_path):
        from app.db.migrations.runner import run_migration
        sql_file = tmp_path / "001_test.sql"
        sql_file.write_text("CREATE TABLE test (id SERIAL);")

        conn = make_mock_conn(already_done=set())

        with patch("psycopg.connect", return_value=conn), \
             patch("app.db.migrations.runner.MIGRATION_DIR", tmp_path), \
             patch.dict("os.environ", {"DATABASE_URL": "postgresql://test"}):
            run_migration()

        executed_sql = [str(c) for c in conn.execute.call_args_list]
        assert any("CREATE TABLE test" in s for s in executed_sql)

    def test_skips_already_applied_migrations(self, tmp_path):
        from app.db.migrations.runner import run_migration
        sql_file = tmp_path / "001_test.sql"
        sql_file.write_text("CREATE TABLE test (id SERIAL);")

        conn = make_mock_conn(already_done={"001_test.sql"})

        with patch("psycopg.connect", return_value=conn), \
             patch("app.db.migrations.runner.MIGRATION_DIR", tmp_path), \
             patch.dict("os.environ", {"DATABASE_URL": "postgresql://test"}):
            run_migration()

        executed_sql = [str(c) for c in conn.execute.call_args_list]
        assert not any("CREATE TABLE test" in s for s in executed_sql)

    def test_applies_migrations_in_sorted_order(self, tmp_path):
        from app.db.migrations.runner import run_migration
        (tmp_path / "002_b.sql").write_text("CREATE TABLE b (id INT);")
        (tmp_path / "001_a.sql").write_text("CREATE TABLE a (id INT);")

        applied = []
        conn = make_mock_conn(already_done=set())
        original_side_effect = conn.execute.side_effect

        def tracking_execute(sql, params=None):
            if "CREATE TABLE a" in sql or "CREATE TABLE b" in sql:
                applied.append(sql.strip().split()[2])  # table name
            return original_side_effect(sql, params)

        conn.execute.side_effect = tracking_execute

        with patch("psycopg.connect", return_value=conn), \
             patch("app.db.migrations.runner.MIGRATION_DIR", tmp_path), \
             patch.dict("os.environ", {"DATABASE_URL": "postgresql://test"}):
            run_migration()

        assert applied == ["a", "b"]

    def test_records_applied_migration_in_table(self, tmp_path):
        from app.db.migrations.runner import run_migration
        (tmp_path / "001_init.sql").write_text("SELECT 1;")

        conn = make_mock_conn(already_done=set())

        with patch("psycopg.connect", return_value=conn), \
             patch("app.db.migrations.runner.MIGRATION_DIR", tmp_path), \
             patch.dict("os.environ", {"DATABASE_URL": "postgresql://test"}):
            run_migration()

        insert_calls = [
            str(c) for c in conn.execute.call_args_list
            if "INSERT INTO migrations" in str(c)
        ]
        assert len(insert_calls) == 1
        assert "001_init.sql" in insert_calls[0]

    def test_closes_connection_when_done(self, tmp_path):
        from app.db.migrations.runner import run_migration
        conn = make_mock_conn()

        with patch("psycopg.connect", return_value=conn), \
             patch("app.db.migrations.runner.MIGRATION_DIR", tmp_path), \
             patch.dict("os.environ", {"DATABASE_URL": "postgresql://test"}):
            run_migration()

        conn.close.assert_called_once()


class TestPendingEmailColumn:
    """pending_email holds an address the user typed and need not own."""

    @staticmethod
    def users_sql() -> str:
        return (Path(__file__).resolve().parents[2] / "app" / "db" / "migrations" / "002_users.sql").read_text()

    def test_column_exists(self):
        assert "pending_email" in self.users_sql()

    def test_pending_email_is_not_unique(self):
        """A unique index would let anyone squat an address (and block its owner from
        using it) just by typing it as a new email without ever confirming."""
        sql = " ".join(line.split("--")[0] for line in self.users_sql().splitlines()).upper()
        assert "UNIQUE INDEX" not in sql or "PENDING_EMAIL" not in sql.split("UNIQUE INDEX", 1)[1]
        assert "PENDING_EMAIL VARCHAR(100) UNIQUE" not in sql

    def test_auth_provider_is_limited_to_the_two_known_values(self):
        sql = self.users_sql()
        assert "auth_provider" in sql and "CHECK (auth_provider IN ('email', 'google'))" in sql
