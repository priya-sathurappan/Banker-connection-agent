"""Builds the platform's components from settings. The only place that knows
which implementation (memory or MongoDB, mock or real OBCV) is in use."""

from dataclasses import dataclass
from typing import Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.mongodb import MongoDBSaver
from pymongo import ASCENDING, MongoClient
from pymongo.collection import Collection

from app.agents.base import AgentDeps
from app.agents.verify_check import VerifyCheckAgent
from app.core.config import Settings
from app.core.llm import NoLLM
from app.core.session_store import MemorySessionStore, MongoSessionStore, SessionStore
from app.orchestrator.registry import AgentRegistry
from app.orchestrator.router import IntentRouter
from app.orchestrator.service import SessionService
from app.tools.obcv import MockObcvClient, ObcvClient


CHECKPOINTS = "bc_checkpoints"
CHECKPOINT_WRITES = "bc_checkpoint_writes"


def sync_ttl_index(collection: Collection, field: str, seconds: int) -> None:
    """Create the TTL index, or change its expiry in place if it already exists.

    MongoDB rejects create_index with a different expireAfterSeconds on an existing
    index, and MongoDBSaver always calls create_index, so a TTL change would otherwise
    fail at startup.
    """
    for index in collection.list_indexes():
        if list(index["key"].items()) == [(field, ASCENDING)]:
            if index.get("expireAfterSeconds") != seconds:
                collection.database.command(
                    "collMod", collection.name, index={"keyPattern": {field: ASCENDING}, "expireAfterSeconds": seconds}
                )
            return
    collection.create_index([(field, ASCENDING)], expireAfterSeconds=seconds)


@dataclass
class Container:
    settings: Settings
    store: SessionStore
    obcv: ObcvClient
    registry: AgentRegistry
    service: SessionService
    mongo_client: Optional[MongoClient] = None

    def close(self) -> None:
        if self.mongo_client is not None:
            self.mongo_client.close()


def build_container(settings: Settings, obcv: Optional[ObcvClient] = None) -> Container:
    mongo_client: Optional[MongoClient] = None
    checkpointer: BaseCheckpointSaver
    if settings.session_store == "mongo":
        mongo_client = MongoClient(settings.mongodb_uri, tz_aware=True, w="majority", readPreference="primary")
        store = MongoSessionStore(mongo_client, settings.mongodb_db, settings.session_ttl_seconds, settings.datacenter)
        db = mongo_client[settings.mongodb_db]
        for name in (CHECKPOINTS, CHECKPOINT_WRITES):
            sync_ttl_index(db[name], "created_at", settings.session_ttl_seconds)
        checkpointer = MongoDBSaver(
            mongo_client,
            db_name=settings.mongodb_db,
            checkpoint_collection_name=CHECKPOINTS,
            writes_collection_name=CHECKPOINT_WRITES,
            ttl=settings.session_ttl_seconds,
        )
    else:
        store = MemorySessionStore(settings.session_ttl_seconds, settings.datacenter)
        checkpointer = InMemorySaver()

    obcv = obcv or MockObcvClient(delay_ms=settings.obcv_mock_delay_ms)
    deps = AgentDeps(settings=settings, store=store, obcv=obcv)
    # Register new agents here.
    registry = AgentRegistry([VerifyCheckAgent()], deps, checkpointer)
    service = SessionService(registry, IntentRouter(NoLLM()), store, deps)
    return Container(settings, store, obcv, registry, service, mongo_client)
