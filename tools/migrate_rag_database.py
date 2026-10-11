from __future__ import annotations

import argparse
import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
import psycopg
from psycopg import Connection
from psycopg.rows import dict_row


REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPO_ROOT / "database" / "migrations"
MIGRATION_NAME_PATTERN = re.compile(r"^\d{3}_[a-z0-9_]+\.sql$")
MIGRATION_LOCK_KEY = "faceguard_evidence_schema_migrations"
TRANSACTION_CONTROL_PATTERN = re.compile(
    r"(?im)^\s*(BEGIN|COMMIT|ROLLBACK)\s*;"
)
LEGACY_TRANSACTION_WRAPPER_PATTERN = re.compile(
    r"\A\s*BEGIN\s*;\s*(?P<body>.*?)\s*COMMIT\s*;\s*\Z",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True, slots=True)
class Migration:
    name: str
    path: Path
    sha256: str
    sql: str


class MigrationError(RuntimeError):
    """Raised when migration history or configuration is invalid."""


def _execution_sql(sql: str, migration_name: str) -> str:
    wrapper_match = LEGACY_TRANSACTION_WRAPPER_PATTERN.fullmatch(sql)
    if wrapper_match is not None:
        body = wrapper_match.group("body").strip()
        if TRANSACTION_CONTROL_PATTERN.search(body):
            raise MigrationError(
                f"Nested migration transaction control is not allowed: "
                f"{migration_name}"
            )
        return body
    if TRANSACTION_CONTROL_PATTERN.search(sql):
        raise MigrationError(
            f"Migration transaction control must be one outer BEGIN/COMMIT "
            f"wrapper: {migration_name}"
        )
    return sql


def discover_migrations(migrations_dir: Path = MIGRATIONS_DIR) -> list[Migration]:
    migrations: list[Migration] = []
    for path in sorted(migrations_dir.glob("*.sql")):
        if not MIGRATION_NAME_PATTERN.fullmatch(path.name):
            raise MigrationError(
                f"Migration filename must match NNN_description.sql: {path.name}"
            )
        sql = path.read_text(encoding="utf-8").strip()
        if not sql:
            raise MigrationError(f"Migration is empty: {path.name}")
        migrations.append(
            Migration(
                name=path.name,
                path=path,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest().upper(),
                sql=_execution_sql(sql, path.name),
            )
        )
    if not migrations:
        raise MigrationError(f"No migrations found in {migrations_dir}.")
    return migrations


def _database_url() -> str:
    load_dotenv(REPO_ROOT / ".env", override=False)
    database_url = os.getenv("RAG_DATABASE_URL", "").strip()
    if not database_url:
        raise MigrationError("RAG_DATABASE_URL is not configured.")
    return database_url


def _ensure_migration_table(connection: Connection) -> None:
    with connection.transaction():
        connection.execute("CREATE SCHEMA IF NOT EXISTS rag")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS rag.schema_migrations (
                migration_name TEXT PRIMARY KEY,
                migration_sha256 TEXT NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT schema_migrations_sha256_format
                    CHECK (migration_sha256 ~ '^[A-F0-9]{64}$')
            )
            """
        )


def _applied_migrations(connection: Connection) -> dict[str, str]:
    rows = connection.execute(
        """
        SELECT migration_name, migration_sha256
        FROM rag.schema_migrations
        ORDER BY migration_name
        """
    ).fetchall()
    return {
        str(row["migration_name"]): str(row["migration_sha256"])
        for row in rows
    }


def apply_migrations(
    connection: Connection,
    migrations: list[Migration],
) -> tuple[int, int]:
    _ensure_migration_table(connection)
    connection.execute(
        "SELECT PG_ADVISORY_LOCK(HASHTEXT(%s))",
        (MIGRATION_LOCK_KEY,),
    )
    try:
        applied = _applied_migrations(connection)
        applied_count = 0
        skipped_count = 0

        for migration in migrations:
            applied_sha256 = applied.get(migration.name)
            if applied_sha256 is not None:
                if applied_sha256 != migration.sha256:
                    raise MigrationError(
                        f"Applied migration checksum changed: {migration.name}"
                    )
                skipped_count += 1
                print(f"Skipped {migration.name} (already applied)")
                continue

            with connection.transaction():
                connection.execute(migration.sql, prepare=False)
                connection.execute(
                    """
                    INSERT INTO rag.schema_migrations (
                        migration_name,
                        migration_sha256
                    ) VALUES (%s, %s)
                    """,
                    (migration.name, migration.sha256),
                )
            applied_count += 1
            print(f"Applied {migration.name}")

        return applied_count, skipped_count
    finally:
        connection.execute(
            "SELECT PG_ADVISORY_UNLOCK(HASHTEXT(%s))",
            (MIGRATION_LOCK_KEY,),
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply versioned FaceGuard Evidence PostgreSQL migrations."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate migration files and database history without applying new files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    migrations = discover_migrations()
    database_url = _database_url()

    with psycopg.connect(
        database_url,
        autocommit=True,
        row_factory=dict_row,
    ) as connection:
        if args.check:
            _ensure_migration_table(connection)
            applied = _applied_migrations(connection)
            for migration in migrations:
                applied_sha256 = applied.get(migration.name)
                if applied_sha256 is not None and applied_sha256 != migration.sha256:
                    raise MigrationError(
                        f"Applied migration checksum changed: {migration.name}"
                    )
            pending = [
                migration.name
                for migration in migrations
                if migration.name not in applied
            ]
            print(f"Migration files valid: {len(migrations)}")
            print(f"Applied migrations: {len(applied)}")
            print(f"Pending migrations: {len(pending)}")
            return

        applied_count, skipped_count = apply_migrations(connection, migrations)
        print(f"Applied this run: {applied_count}")
        print(f"Already applied: {skipped_count}")


if __name__ == "__main__":
    main()
