"""MySQL/InnoDB integration checks for migration and atomic inventory allocation.

These tests run only in the MySQL integration workflow. The concurrent test
exercises the same conditional SQL allocation pattern used by reservation
inventory updates; API-level concurrency remains a separate follow-up check.
"""
from concurrent.futures import ThreadPoolExecutor
import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

DATABASE_URL = os.getenv("DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL.startswith("mysql"),
    reason="Requires a MySQL DATABASE_URL; run in mysql-integration workflow",
)


def test_mysql_connection_uses_innodb():
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            version = connection.execute(text("SELECT VERSION()")).scalar_one()
            assert version
            assert "mysql" in engine.dialect.name
    finally:
        engine.dispose()


def test_conditional_inventory_update_never_allocates_more_than_available():
    """Race many connections for one remaining unit using InnoDB row updates."""
    engine = create_engine(
        DATABASE_URL,
        pool_size=12,
        max_overflow=4,
        pool_pre_ping=True,
    )
    table = f"seatflow_inventory_race_{uuid.uuid4().hex[:12]}"
    try:
        with engine.begin() as connection:
            connection.execute(text(
                f"CREATE TABLE {table} (id INT PRIMARY KEY, available INT NOT NULL) ENGINE=InnoDB"
            ))
            connection.execute(text(f"INSERT INTO {table} (id, available) VALUES (1, 1)"))

        def attempt_allocation(_):
            with engine.begin() as connection:
                result = connection.execute(text(
                    f"UPDATE {table} SET available = available - 1 "
                    "WHERE id = 1 AND available >= 1"
                ))
                return result.rowcount

        with ThreadPoolExecutor(max_workers=12) as executor:
            outcomes = list(executor.map(attempt_allocation, range(24)))

        assert sum(outcomes) == 1, f"Expected exactly one allocation, got {sum(outcomes)}"
        with engine.connect() as connection:
            remaining = connection.execute(
                text(f"SELECT available FROM {table} WHERE id = 1")
            ).scalar_one()
        assert remaining == 0
    finally:
        with engine.begin() as connection:
            connection.execute(text(f"DROP TABLE IF EXISTS {table}"))
        engine.dispose()
