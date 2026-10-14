"""Session retention: TTL indexes follow BCW_SESSION_TTL_SECONDS, including when it changes."""

from pymongo import MongoClient

from app.core.config import Settings
from app.core.container import CHECKPOINT_WRITES, CHECKPOINTS, build_container
from tests.conftest import MONGO_URI

THIRTY_DAYS = 30 * 24 * 60 * 60


def ttl_seconds(db, collection: str, field: str):
    return next(i.get("expireAfterSeconds") for i in db[collection].list_indexes() if field in i["key"])


def test_default_retention_is_30_days():
    assert Settings().session_ttl_seconds == THIRTY_DAYS


def test_changing_ttl_on_an_existing_database_updates_indexes(mongo_db):
    for ttl in (1800, THIRTY_DAYS):
        settings = Settings(session_store="mongo", mongodb_uri=MONGO_URI, mongodb_db=mongo_db, session_ttl_seconds=ttl)
        build_container(settings).close()

    db = MongoClient(MONGO_URI)[mongo_db]
    assert ttl_seconds(db, CHECKPOINTS, "created_at") == THIRTY_DAYS
    assert ttl_seconds(db, CHECKPOINT_WRITES, "created_at") == THIRTY_DAYS
    # Sessions expire at their own expires_at, set 30 days after the last step.
    assert ttl_seconds(db, "bc_sessions", "expires_at") == 0
