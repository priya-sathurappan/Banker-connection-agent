"""OBCV (check verification) client interface.

Agents depend on this interface only. The mock implements it today; the real
OBCV adapter will implement it once the API specification is available.
"""

from typing import Literal, Protocol

from pydantic import BaseModel


class ObcvRequest(BaseModel):
    serial_number: str
    routing_number: str
    account_number: str
    check_number: str
    payee: str
    amount: str
    issued_date: str  # YYYY-MM-DD


class ObcvResult(BaseModel):
    status: Literal["OK_TO_NEGOTIATE", "REFER"]
    reference: str
    message: str

    @property
    def ok(self) -> bool:
        return self.status == "OK_TO_NEGOTIATE"


class ObcvUnavailable(Exception):
    """OBCV could not be reached or returned an error."""


class ObcvClient(Protocol):
    def verify(self, request: ObcvRequest, idempotency_key: str) -> ObcvResult:
        """Verify a check. The same idempotency key must never verify twice."""
        ...
