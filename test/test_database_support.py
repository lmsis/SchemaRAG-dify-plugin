#!/usr/bin/env python3
"""
Database support: connection string generation smoke test.
"""

import sys
import os

# Project root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DatabaseConfig


def test_database_connections():
    """Print connection strings for each supported DB type."""

    test_configs = [
        {
            "type": "mysql",
            "host": "localhost",
            "port": 3306,
            "user": "root",
            "password": "password",
            "database": "test_db",
        },
        {
            "type": "postgresql",
            "host": "localhost",
            "port": 5432,
            "user": "postgres",
            "password": "password",
            "database": "test_db",
        },
        {
            "type": "mssql",
            "host": "localhost",
            "port": 1433,
            "user": "sa",
            "password": "password",
            "database": "test_db",
        },
        {
            "type": "oracle",
            "host": "localhost",
            "port": 1521,
            "user": "system",
            "password": "password",
            "database": "ORCL",
        },
        {
            "type": "dameng",
            "host": "localhost",
            "port": 5236,
            "user": "SYSDBA",
            "password": "SYSDBA",
            "database": "test_db",
        },
    ]

    print("Database connection string generation:")
    print("=" * 60)

    for config in test_configs:
        try:
            db_config = DatabaseConfig(
                type=config["type"],
                host=config["host"],
                port=config["port"],
                user=config["user"],
                password=config["password"],
                database=config["database"],
            )

            connection_string = db_config.get_connection_string()
            print(f"✅ {config['type'].upper():>12}: {connection_string}")

        except Exception as e:
            print(f"❌ {config['type'].upper():>12}: error - {e}")

    print("=" * 60)


if __name__ == "__main__":
    test_database_connections()
