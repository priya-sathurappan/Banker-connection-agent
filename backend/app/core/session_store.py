"""Session store: the only shared state between datacenters.

Two implementations behind one interface:
- MemorySessionStore: local development and tests.
- MongoSessionStore: production, on the shared MongoDB cluster (majority writes,
  primary reads, TTL expiry).

The workflow's own state is saved separately by the LangGraph checkpointer
(see checkpointer.py); this store holds the session record, its status, the
OBCV result and the audit trail.
"""

import copy
import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from pymongo import ASCENDING, MongoClient, ReadPreference
from pymongo.errors import PyMongoError
from pymongo.write_concern import WriteConcern


class SessionNotFound(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SessionStore(ABC):
    def __init__(self, ttl_seconds: int, datacenter: str):
        self.ttl_seconds = ttl_seconds
        self.datacenter = datacenter

    def _new_record(self, session_id: str, agent: str, started_by: Optional[str]) -> dict[str, Any]:
        now = _now()
        return {
            "_id": session_id,
            "agent": agent,
            "status": "active",
            "started_by": started_by,
            "created_at": now,
            "updated_at": now,
            "expires_at": now + timedelta(seconds=self.ttl_seconds),
            "last_dc": self.datacenter,
            "obcv_result": None,
            "events": [],
        }

    def _touch(self) -> dict[str, Any]:
        now = _now()
        return {
            "updated_at": now,
            "expires_at": now + timedelta(seconds=self.ttl_seconds),
            "last_dc": self.datacenter,
        }

    @abstractmethod
    def create(self, session_id: str, agent: str, started_by: Optional[str]) -> dict[str, Any]: ...

    @abstractmethod
    def get(self, session_id: str) -> dict[str, Any]:
        """Return the session, or raise SessionNotFound if missing or expired."""

    @abstractmethod
    def update(self, session_id: str, **fields: Any) -> None: ...

    @abstractmethod
    def add_event(self, session_id: str, event: dict[str, Any]) -> None:
        """Append an audit event. Events must never contain PII."""

    @abstractmethod
    def claim(self, session_id: str, from_status: str, to_status: str) -> bool:
        """Atomically move the status from one value to another.

        Returns True for exactly one caller, even when several servers in
        different datacenters try at the same time.
        """

    def wait_for_obcv_result(self, session_id: str, timeout_seconds: float) -> Optional[dict[str, Any]]:
        """Wait for another server's OBCV call to store its result."""
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            result = self.get(session_id).get("obcv_result")
            if result is not None:
                return result
            time.sleep(0.2)
        return None

    def ping(self) -> bool:
        return True


class MemorySessionStore(SessionStore):
    def __init__(self, ttl_seconds: int, datacenter: str):
        super().__init__(ttl_seconds, datacenter)
        self._sessions: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create(self, session_id, agent, started_by):
        record = self._new_record(session_id, agent, started_by)
        with self._lock:
            self._sessions[session_id] = record
        return copy.deepcopy(record)

    def _live(self, session_id: str) -> dict[str, Any]:
        record = self._sessions.get(session_id)
        if record is None or record["expires_at"] <= _now():
            raise SessionNotFound(session_id)
        return record

    def get(self, session_id):
        with self._lock:
            return copy.deepcopy(self._live(session_id))

    def update(self, session_id, **fields):
        with self._lock:
            self._live(session_id).update(fields, **self._touch())

    def add_event(self, session_id, event):
        with self._lock:
            record = self._live(session_id)
            record["events"].append({"at": _now(), "dc": self.datacenter, **event})

    def claim(self, session_id, from_status, to_status):
        with self._lock:
            record = self._live(session_id)
            if record["status"] != from_status:
                return False
            record.update(status=to_status, **self._touch())
            return True


class MongoSessionStore(SessionStore):
    COLLECTION = "bc_sessions"

    def __init__(self, client: MongoClient, db_name: str, ttl_seconds: int, datacenter: str):
        super().__init__(ttl_seconds, datacenter)
        self._client = client
        # Majority writes + primary reads: a step saved through one datacenter is
        # visible immediately to a request that lands in another.
        self._sessions = client[db_name].get_collection(
            self.COLLECTION,
            write_concern=WriteConcern("majority"),
            read_preference=ReadPreference.PRIMARY,
        )
        # MongoDB removes a document once its expires_at passes.
        self._sessions.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)

    def create(self, session_id, agent, started_by):
        record = self._new_record(session_id, agent, started_by)
        self._sessions.insert_one(record)
        return record

    def get(self, session_id):
        # The TTL monitor runs about once a minute, so check expiry ourselves too.
        record = self._sessions.find_one({"_id": session_id, "expires_at": {"$gt": _now()}})
        if record is None:
            raise SessionNotFound(session_id)
        return record

    def update(self, session_id, **fields):
        result = self._sessions.update_one({"_id": session_id}, {"$set": {**fields, **self._touch()}})
        if result.matched_count == 0:
            raise SessionNotFound(session_id)

    def add_event(self, session_id, event):
        entry = {"at": _now(), "dc": self.datacenter, **event}
        result = self._sessions.update_one({"_id": session_id}, {"$push": {"events": entry}})
        if result.matched_count == 0:
            raise SessionNotFound(session_id)

    def claim(self, session_id, from_status, to_status):
        result = self._sessions.update_one(
            {"_id": session_id, "status": from_status, "expires_at": {"$gt": _now()}},
            {"$set": {"status": to_status, **self._touch()}},
        )
        return result.modified_count == 1

    def ping(self) -> bool:
        try:
            self._client.admin.command("ping")
            return True
        except PyMongoError:
            return False
