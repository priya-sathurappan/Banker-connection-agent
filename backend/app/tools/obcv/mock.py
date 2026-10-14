"""Mock OBCV service for phase 1.

Behaviour (for testing the flows, mock only):
- Check # starting with "999" -> REFER (the check cannot be negotiated).
- Check # starting with "000" -> OBCV unavailable (simulated outage).
- Anything else -> OK_TO_NEGOTIATE.
The reference is derived from the idempotency key, so a repeated call for the
same session returns the same reference.
"""

import hashlib
import logging
import threading
import time

from app.core.logging import log, mask
from app.tools.obcv.client import ObcvRequest, ObcvResult, ObcvUnavailable

logger = logging.getLogger(__name__)


class MockObcvClient:
    def __init__(self, delay_ms: int = 0):
        self.delay_ms = delay_ms
        self.calls = 0
        self._results: dict[str, ObcvResult] = {}
        self._lock = threading.Lock()

    def verify(self, request: ObcvRequest, idempotency_key: str) -> ObcvResult:
        with self._lock:
            self.calls += 1
            cached = self._results.get(idempotency_key)
        if cached is not None:
            return cached

        log(
            logger,
            "obcv.mock.verify",
            account=mask(request.account_number),
            routing=mask(request.routing_number),
            check=mask(request.check_number),
        )
        if self.delay_ms:
            time.sleep(self.delay_ms / 1000)

        if request.check_number.startswith("000"):
            raise ObcvUnavailable("Mock OBCV outage")

        digest = int(hashlib.sha256(idempotency_key.encode()).hexdigest(), 16)
        reference = f"OBCV-{digest % 1_000_000:06d}"
        if request.check_number.startswith("999"):
            result = ObcvResult(status="REFER", reference=reference, message="Check cannot be negotiated.")
        else:
            result = ObcvResult(
                status="OK_TO_NEGOTIATE",
                reference=reference,
                message="The check is valid — no stops, holds, or duplicate presentments were found.",
            )
        with self._lock:
            self._results[idempotency_key] = result
        return result
