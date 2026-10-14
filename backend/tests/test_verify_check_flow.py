"""Every branch of the Verify check workflow, on both stores."""

from tests.flow import DETAILS_OK, ELIGIBILITY_OK, PREVALIDATION_OK, alert, start, submit, to_details

REQUIRED = "This field is required."


def test_first_screen_is_prevalidation(client):
    c, _ = client
    view = start(c)
    assert view["status"] == "active"
    assert view["screen"]["step"] == "prevalidation"
    assert view["screen"]["heading"] == "Pre-validation"
    assert [b["id"] for b in view["screen"]["blocks"]] == ["identity_verified", "wf_issued"]
    assert view["completed_steps"] == []


def test_happy_path_ends_ok_to_negotiate(client):
    c, container = client
    view = start(c)
    view = submit(c, view, PREVALIDATION_OK)
    assert view["screen"]["step"] == "eligibility"
    assert [s["title"] for s in view["completed_steps"]] == ["Pre-validation"]

    view = submit(c, view, ELIGIBILITY_OK)
    assert view["screen"]["step"] == "check_details"
    assert view["screen"]["actions"][-1]["progress_label"] == "Running OBCV verification…"

    view = submit(c, view, DETAILS_OK)
    assert view["status"] == "completed"
    screen = view["screen"]
    assert screen["heading"] == "Verification complete"
    assert alert(view)["title"] == "Ok to Negotiate"
    summary = {i["label"]: i["value"] for i in screen["blocks"][1]["items"]}
    assert summary["Reference"].startswith("OBCV-")
    assert summary["Amount"] == "$1,250.50"
    assert summary["Issued"] == "10/02/2026"
    assert [s["title"] for s in view["completed_steps"]] == ["Pre-validation", "Eligibility", "Check details"]
    assert container.obcv.calls == 1


def test_account_and_routing_are_masked_in_completed_steps(client):
    c, _ = client
    view = submit(c, to_details(c), DETAILS_OK)
    details = {i["label"]: i["value"] for i in view["completed_steps"][2]["items"]}
    assert details["Account #"] == "******7890"
    assert details["Routing #"] == "*****0248"


def test_continue_without_answers_shows_required_errors(client):
    c, _ = client
    view = submit(c, start(c), {})
    assert view["screen"]["step"] == "prevalidation"
    assert view["screen"]["errors"] == {"identity_verified": REQUIRED, "wf_issued": REQUIRED}


def test_partial_answers_are_kept_on_error(client):
    c, _ = client
    view = submit(c, start(c), {"identity_verified": True})
    assert view["screen"]["errors"] == {"wf_issued": REQUIRED}
    assert view["screen"]["values"]["identity_verified"] is True
    view = submit(c, view, PREVALIDATION_OK)
    assert view["screen"]["step"] == "eligibility"


def test_not_issued_by_wells_fargo_stops(client):
    c, _ = client
    view = submit(c, start(c), {"identity_verified": True, "wf_issued": "no"})
    assert view["status"] == "stopped"
    assert alert(view)["title"] == "Follow the standard procedure"
    assert alert(view)["message"] == "Only checks issued by Wells Fargo can be verified in this workflow."
    assert alert(view)["link"] == {"label": "Contact the Banker Connection Team", "href": "https://bc.test/contact"}
    assert view["screen"]["actions"] == [
        {"id": "close", "label": "Close", "kind": "close", "variant": "primary", "progress_label": None}
    ]


def test_instrument_not_presented_stops(client):
    c, _ = client
    view = submit(c, start(c), PREVALIDATION_OK)
    view = submit(c, view, {"presented": "no", "account_type": "non_deposit"})
    assert view["status"] == "stopped"
    assert alert(view)["title"] == "Follow the standard procedure"


def test_deposit_account_stops(client):
    c, _ = client
    view = submit(c, start(c), PREVALIDATION_OK)
    view = submit(c, view, {"presented": "yes", "account_type": "deposit"})
    assert view["status"] == "stopped"
    assert alert(view)["message"] == "Checks associated with a deposit account can't be verified in this workflow."


def test_unknown_choice_value_counts_as_missing(client):
    c, _ = client
    view = submit(c, start(c), PREVALIDATION_OK)
    view = submit(c, view, {"presented": "maybe", "account_type": "non_deposit"})
    assert view["screen"]["errors"] == {"presented": REQUIRED}


def test_check_details_all_required(client):
    c, container = client
    view = submit(c, to_details(c), {"payee": "   "})
    assert view["screen"]["step"] == "check_details"
    assert set(view["screen"]["errors"]) == set(DETAILS_OK)
    assert container.obcv.calls == 0


def test_obcv_refer_stops(client):
    c, _ = client
    view = submit(c, to_details(c), {**DETAILS_OK, "check_number": "99901"})
    assert view["status"] == "stopped"
    assert "OBCV couldn't confirm" in alert(view)["message"]


def test_obcv_outage_stops_without_wrong_result(client):
    c, _ = client
    view = submit(c, to_details(c), {**DETAILS_OK, "check_number": "00042"})
    assert view["status"] == "stopped"
    assert "unavailable" in alert(view)["message"]


def test_cancel_ends_session(client):
    c, _ = client
    view = submit(c, start(c), {}, action="cancel")
    assert view["status"] == "cancelled"
    assert view["screen"] is None
    again = submit(c, view, PREVALIDATION_OK, step="prevalidation")
    assert again["status"] == "cancelled"


def test_stale_step_submit_changes_nothing(client):
    c, _ = client
    view = submit(c, start(c), PREVALIDATION_OK)
    stale = submit(c, view, {"identity_verified": True, "wf_issued": "no"}, step="prevalidation")
    assert stale["status"] == "active"
    assert stale["screen"]["step"] == "eligibility"


def test_resubmitting_details_after_completion_does_not_call_obcv_again(client):
    c, container = client
    details = to_details(c)
    done = submit(c, details, DETAILS_OK)
    again = submit(c, details, DETAILS_OK, step="check_details")
    assert again["status"] == "completed"
    assert again["screen"]["blocks"][1] == done["screen"]["blocks"][1]
    assert container.obcv.calls == 1


def test_get_session_returns_current_screen(client):
    c, _ = client
    view = submit(c, start(c), PREVALIDATION_OK)
    fetched = c.get(f"/api/v1/sessions/{view['session_id']}").json()
    assert fetched == view


def test_unknown_session_is_404(client):
    c, _ = client
    assert c.get("/api/v1/sessions/nope").status_code == 404
    response = c.post("/api/v1/sessions/nope/submit", json={"step": "prevalidation", "values": {}})
    assert response.status_code == 404


def test_free_text_routes_to_verify_check(client):
    c, _ = client
    view = start(c, text="Customer wants me to verify a check")
    assert view["agent"] == "verify_check"


def test_unknown_intent_is_422(client):
    c, _ = client
    assert c.post("/api/v1/sessions", json={"intent": "open_account"}).status_code == 422
    assert c.post("/api/v1/sessions", json={"text": "hello there"}).status_code == 422


def test_audit_trail_has_no_check_details(client):
    c, container = client
    view = submit(c, to_details(c), DETAILS_OK)
    events = container.store.get(view["session_id"])["events"]
    assert [e["type"] for e in events] == ["started", "submitted", "submitted", "obcv", "submitted", "finished"]
    assert "1234567890" not in str(events)


def test_health(client):
    c, _ = client
    assert c.get("/health/live").json() == {"status": "ok"}
    assert c.get("/health/ready").json() == {"status": "ok", "datacenter": "dc-test"}
    assert c.get("/health/live").headers["X-Datacenter"] == "dc-test"


def test_correlation_id_is_echoed(client):
    c, _ = client
    response = c.get("/health/live", headers={"X-Correlation-ID": "abc123"})
    assert response.headers["X-Correlation-ID"] == "abc123"
