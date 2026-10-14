# Banker Connection Agent

Banker Connection (BC) workflows: a React micro-frontend backed by a Python agent platform.
Phase 1 delivers **Verify check** end to end against a mock OBCV service.

| Folder | What | Deployed as |
| --- | --- | --- |
| [`frontend/`](frontend) | React + TypeScript MFE, Webpack 5 Module Federation remote | Static files (incl. `remoteEntry.js`) in each datacenter |
| [`backend/`](backend) | FastAPI agent platform: orchestrator, agent registry, LangGraph agents, tools | Docker image in each datacenter |

The two apps are independent: separate builds, tests and deployments. The only thing they share is the
UI-block contract in [`backend/app/core/schemas.py`](backend/app/core/schemas.py) and
[`frontend/src/api/types.ts`](frontend/src/api/types.ts), so change both together.

## How it works

1. The parent container loads the MFE (`remoteEntry.js`) and renders `BcWorkflows` (or calls `mount`).
2. **Verify check** starts a session: `POST /api/v1/sessions {"intent": "verify_check"}`.
3. The `verify_check` agent (a LangGraph graph) pauses at each step and the backend returns the screen as
   typed UI blocks. The MFE renders them and posts the answers to `/api/v1/sessions/{id}/submit`.
4. The business rules (issued by Wells Fargo, check presented, non-deposit account, required fields) are
   deterministic graph nodes, never LLM decisions.
5. Session state lives in MongoDB (sessions + LangGraph checkpoints), so any server in any of the four
   datacenters can serve any step. OBCV is called at most once per session (atomic claim in MongoDB).

## Run locally

Prerequisites: Python 3.11+, Node 20+, and MongoDB 8.0 on `127.0.0.1:27017` (optional: the backend
also runs on an in-memory store).

**Backend** (http://127.0.0.1:8000, API docs at `/docs`):

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt     # macOS/Linux: .venv/bin/pip
cp .env.example .env                                  # set BCW_SESSION_STORE=mongo to use MongoDB
.venv/Scripts/python -m uvicorn app.main:app --port 8000 --env-file .env
```

**Frontend** (standalone harness at http://localhost:3000, no props needed):

```bash
cd frontend
npm install
npm start
```

## Tests

```bash
cd backend
BCW_TEST_MONGODB_URI=mongodb://127.0.0.1:27017 .venv/Scripts/python -m pytest
```

Every flow test runs on both stores; without `BCW_TEST_MONGODB_URI` the MongoDB runs are skipped.
`tests/test_multi_datacenter.py` runs two app instances on one database to prove a session continues
across datacenters and that concurrent submits call OBCV once.

```bash
cd frontend
npm run typecheck
npm test
npm run build
```

## Mock OBCV test data

| Check # starts with | Result |
| --- | --- |
| `999` | REFER: "Follow the standard procedure" |
| `000` | OBCV unavailable: "Follow the standard procedure" |
| anything else | Ok to Negotiate |

## Integrating the MFE in the parent container

Webpack Module Federation remote name `bcWorkflows`, entry `remoteEntry.js`. Exposed modules:

- `./BcWorkflows`: React component (React and React DOM are shared singletons).
- `./mount`: `mount(element, props)` returns an `unmount()` function, for non-React parents.

Props (all optional):

| Prop | Purpose | Default |
| --- | --- | --- |
| `apiBaseUrl` | Backend address | `config.json` next to `remoteEntry.js`, then `http://127.0.0.1:8000` |
| `authToken` | Sent as `Authorization: Bearer …` | none |
| `user` | `{ id, name }` of the banker; `id` is sent as `X-Banker-Id` for audit | none |
| `onClose` | Called when the banker leaves a workflow | no-op |
| `onEvent` | Lifecycle events (`workflow_started`, `workflow_finished`, `workflow_cancelled`) | no-op |

The MFE never changes the URL. Serve `remoteEntry.js` and `config.json` with `Cache-Control: no-cache`;
every other file is content-hashed and can be cached long term.

## Backend configuration

All settings are environment variables with the `BCW_` prefix; see
[`backend/.env.example`](backend/.env.example). In production: `BCW_SESSION_STORE=mongo`, the shared
cluster's `BCW_MONGODB_URI`, and `BCW_DATACENTER` set per datacenter.

## Adding a new use case

1. Create an agent under `backend/app/agents/<name>/` implementing `Agent` (graph, screens, keywords).
2. Register it in `build_container` in [`backend/app/core/container.py`](backend/app/core/container.py).
3. Put any new integration behind an interface in `backend/app/tools/`, with a mock.
4. Reuse the existing UI blocks; only a new block type needs an MFE change.
