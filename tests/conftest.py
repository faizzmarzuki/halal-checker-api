"""Test-wide environment setup. Runs before test modules are imported."""
import os
import tempfile

os.environ.setdefault("HALAL_JWT_SECRET", "test-secret")
# Each test run gets its own throwaway SQLite file.
_db_path = os.path.join(tempfile.gettempdir(), "halal_test.db")
os.environ.setdefault("HALAL_DATABASE_URL", f"sqlite:///{_db_path}")
