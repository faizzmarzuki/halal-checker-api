from halal_scanner.db import _normalize_db_url


def test_sqlite_url_unchanged():
    assert _normalize_db_url("sqlite:///./halal_scanner.db") == "sqlite:///./halal_scanner.db"


def test_heroku_style_postgres_scheme_maps_to_psycopg3():
    assert (
        _normalize_db_url("postgres://u:p@host:5432/db")
        == "postgresql+psycopg://u:p@host:5432/db"
    )


def test_plain_postgresql_scheme_maps_to_psycopg3():
    assert (
        _normalize_db_url("postgresql://u:p@host:5432/db")
        == "postgresql+psycopg://u:p@host:5432/db"
    )


def test_explicit_driver_left_unchanged():
    assert (
        _normalize_db_url("postgresql+psycopg2://u:p@host/db")
        == "postgresql+psycopg2://u:p@host/db"
    )
    assert (
        _normalize_db_url("postgresql+psycopg://u:p@host/db")
        == "postgresql+psycopg://u:p@host/db"
    )
