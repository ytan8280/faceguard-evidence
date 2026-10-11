from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from tools.migrate_rag_database import MigrationError, discover_migrations


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_discover_migrations_returns_versioned_files() -> None:
    migrations = discover_migrations(
        REPOSITORY_ROOT / "database" / "migrations"
    )

    assert [migration.name for migration in migrations] == [
        "001_create_rag_core.sql"
    ]
    assert all(len(migration.sha256) == 64 for migration in migrations)
    assert all(migration.sql for migration in migrations)


def test_discover_migrations_strips_outer_transaction_wrapper(
    tmp_path: Path,
) -> None:
    migration_path = tmp_path / "001_wrapped.sql"
    migration_path.write_text(
        "BEGIN;\nCREATE TABLE example (id INTEGER);\nCOMMIT;\n",
        encoding="utf-8",
    )

    migrations = discover_migrations(tmp_path)

    assert migrations[0].sql == "CREATE TABLE example (id INTEGER);"
    assert migrations[0].sha256 == hashlib.sha256(
        migration_path.read_bytes()
    ).hexdigest().upper()


def test_discover_migrations_rejects_nested_transaction_control(
    tmp_path: Path,
) -> None:
    migration_path = tmp_path / "001_invalid.sql"
    migration_path.write_text(
        "BEGIN;\nCREATE TABLE example (id INTEGER);\nROLLBACK;\nCOMMIT;\n",
        encoding="utf-8",
    )

    with pytest.raises(MigrationError, match="Nested migration transaction"):
        discover_migrations(tmp_path)


def test_discover_migrations_rejects_invalid_filename(tmp_path: Path) -> None:
    (tmp_path / "migration.sql").write_text(
        "CREATE TABLE example (id INTEGER);\n",
        encoding="utf-8",
    )

    with pytest.raises(MigrationError, match="filename"):
        discover_migrations(tmp_path)
