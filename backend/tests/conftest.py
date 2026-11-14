"""API tests run against a real Postgres database (the models use ARRAY).

Uses TEST_DATABASE_URL, or DATABASE_URL with "_test" added to the database
name. The database is created on first use and emptied before every test.
"""

import os

import psycopg2
import pytest
from dotenv import load_dotenv
from sqlalchemy.engine import make_url

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def _test_url():
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return make_url(explicit)
    base = make_url(os.environ.get(
        "DATABASE_URL", "postgresql://chronos:chronos@localhost:5432/chronos"))
    return base.set(database=f"{base.database}_test")


@pytest.fixture(scope="session")
def app():
    from app import create_app
    from app.extensions import db

    url = _test_url()
    try:
        admin = psycopg2.connect(
            host=url.host, port=url.port or 5432, user=url.username,
            password=url.password, dbname="postgres", connect_timeout=5)
    except psycopg2.OperationalError as e:
        pytest.skip(f"Postgres not reachable, API tests skipped: {e}")
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (url.database,))
        if not cur.fetchone():
            cur.execute(f'CREATE DATABASE "{url.database}"')
    admin.close()

    app = create_app(url.render_as_string(hide_password=False))
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app


@pytest.fixture
def client(app):
    from app.extensions import db

    db.session.remove()
    tables = ", ".join(f'"{t.name}"' for t in db.metadata.sorted_tables)
    db.session.execute(db.text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    db.session.commit()
    return app.test_client()
