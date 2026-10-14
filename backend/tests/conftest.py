"""Test fixtures.

Every test that uses `make_client` runs twice: once on the in-memory store and
once on MongoDB. MongoDB runs only when BCW_TEST_MONGODB_URI is set, e.g.
    BCW_TEST_MONGODB_URI=mongodb://127.0.0.1:27017
Each MongoDB test gets its own throwaway database.
"""

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

from app.core.config import Settings
from app.core.container import build_container
from app.main import create_app
from app.tools.obcv import MockObcvClient

MONGO_URI = os.environ.get("BCW_TEST_MONGODB_URI")


@pytest.fixture(params=["memory", "mongo"])
def store_kind(request):
    if request.param == "mongo" and not MONGO_URI:
        pytest.skip("BCW_TEST_MONGODB_URI not set")
    return request.param


@pytest.fixture
def mongo_db():
    if not MONGO_URI:
        pytest.skip("BCW_TEST_MONGODB_URI not set")
    name = f"bcw_test_{uuid.uuid4().hex[:12]}"
    yield name
    client = MongoClient(MONGO_URI)
    client.drop_database(name)
    client.close()


def _settings(kind: str, db_name: str, datacenter: str) -> Settings:
    return Settings(
        session_store=kind,
        mongodb_uri=MONGO_URI or "mongodb://127.0.0.1:27017",
        mongodb_db=db_name,
        datacenter=datacenter,
        obcv_mock_delay_ms=0,
        obcv_wait_timeout_seconds=10,
        bc_team_url="https://bc.test/contact",
        log_level="WARNING",
    )


@pytest.fixture
def make_client():
    """Build a TestClient on a given store; clients sharing a db_name share state (MongoDB only)."""
    opened = []

    def factory(kind: str, db_name: str = "", datacenter: str = "dc-test", obcv=None):
        container = build_container(_settings(kind, db_name, datacenter), obcv or MockObcvClient())
        client = TestClient(create_app(container=container))
        client.__enter__()
        opened.append(client)
        return client, container

    yield factory
    for client in opened:
        client.__exit__(None, None, None)


@pytest.fixture
def client(store_kind, make_client, request):
    db_name = ""
    if store_kind == "mongo":
        db_name = request.getfixturevalue("mongo_db")
    return make_client(store_kind, db_name)
