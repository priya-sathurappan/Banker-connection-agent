from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.core.container import Container
from app.core.schemas import AgentInfo, SessionView, StartSessionRequest, SubmitRequest
from app.core.session_store import SessionNotFound
from app.orchestrator.service import UnknownIntent

router = APIRouter(prefix="/api/v1")
health = APIRouter(prefix="/health", tags=["health"])


def container(request: Request) -> Container:
    return request.app.state.container


def caller(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_banker_id: Optional[str] = Header(default=None),
) -> Optional[str]:
    """Identify the banker. Token validation against enterprise SSO is a later step."""
    settings = container(request).settings
    if settings.auth_required and not (authorization or "").lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    return x_banker_id


@router.get("/agents", response_model=list[AgentInfo])
def list_agents(c: Container = Depends(container), _: Optional[str] = Depends(caller)):
    return [AgentInfo(name=a.name, title=a.title, description=a.description) for a in c.registry.all()]


@router.post("/sessions", response_model=SessionView, status_code=status.HTTP_201_CREATED)
def start_session(
    body: StartSessionRequest, c: Container = Depends(container), banker: Optional[str] = Depends(caller)
):
    try:
        return c.service.start(body.intent, body.text, banker)
    except UnknownIntent:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "No workflow matches this request")


@router.get("/sessions/{session_id}", response_model=SessionView)
def get_session(session_id: str, c: Container = Depends(container), _: Optional[str] = Depends(caller)):
    try:
        return c.service.get(session_id)
    except SessionNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found or expired")


@router.post("/sessions/{session_id}/submit", response_model=SessionView)
def submit_step(
    session_id: str, body: SubmitRequest, c: Container = Depends(container), _: Optional[str] = Depends(caller)
):
    try:
        return c.service.submit(session_id, body.step, body.action, body.values)
    except SessionNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found or expired")


@health.get("/live")
def live():
    return {"status": "ok"}


@health.get("/ready")
def ready(c: Container = Depends(container)):
    if not c.store.ping():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Session store unavailable")
    return {"status": "ok", "datacenter": c.settings.datacenter}
