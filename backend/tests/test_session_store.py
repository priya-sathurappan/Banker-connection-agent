"""Session store contract, on both implementations."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from pymongo import MongoClient

from app.core.session_store import MemorySessionStore, MongoSessionStore, SessionNotFound
from tests.conftest import MONGO_URI


@pytest.fixture
def store(store_kind, request):
    if store_kind == "memory":
        yield MemorySessionStore(ttl_seconds=60, datacenter="dc-test")
        return
    db_name = request.getfixturevalue("mongo_db")
    client = MongoClient(MONGO_URI, tz_aware=True)
    yield MongoSessionStore(client, db_name, ttl_seconds=60, datacenter="dc-test")
    client.close()


def test_create_get_update(store):
    store.create("s1", "verify_check", "banker-1")
    store.update("s1", step="eligibility")
    record = store.get("s1")
    assert record["agent"] == "verify_check"
    assert record["started_by"] == "banker-1"
    assert record["status"] == "active"
    assert record["step"] == "eligibility"
    assert record["last_dc"] == "dc-test"


def test_missing_session_raises(store):
    with pytest.raises(SessionNotFound):
        store.get("missing")
    with pytest.raises(SessionNotFound):
        store.update("missing", step="x")


def test_claim_succeeds_exactly_once_under_contention(store):
    store.create("s1", "verify_check", None)
    with ThreadPoolExecutor(max_workers=8) as pool:
        wins = list(pool.map(lambda _: store.claim("s1", "active", "verifying"), range(8)))
    assert wins.count(True) == 1
    assert store.get("s1")["status"] == "verifying"


def test_expired_session_is_not_found(store):
    store.ttl_seconds = -1
    store.create("old", "verify_check", None)
    with pytest.raises(SessionNotFound):
        store.get("old")
