"""Helpers that drive the Verify check flow through the API."""

PREVALIDATION_OK = {"identity_verified": True, "wf_issued": "yes"}
ELIGIBILITY_OK = {"presented": "yes", "account_type": "non_deposit"}
DETAILS_OK = {
    "serial_number": "12",
    "routing_number": "121000248",
    "account_number": "1234567890",
    "check_number": "23423",
    "payee": "Jane Doe",
    "amount": "1250.5",
    "issued_date": "2026-10-02",
}


def start(client, **body):
    response = client.post("/api/v1/sessions", json=body or {"intent": "verify_check"})
    assert response.status_code == 201, response.text
    return response.json()


def submit(client, view, values, action="continue", step=None):
    response = client.post(
        f"/api/v1/sessions/{view['session_id']}/submit",
        json={"step": step or view["screen"]["step"], "action": action, "values": values},
    )
    assert response.status_code == 200, response.text
    return response.json()


def to_details(client):
    view = start(client)
    view = submit(client, view, PREVALIDATION_OK)
    return submit(client, view, ELIGIBILITY_OK)


def alert(view):
    return next(b for b in view["screen"]["blocks"] if b["type"] == "alert")
