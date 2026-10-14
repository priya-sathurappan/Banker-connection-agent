"""Back button: return to the previous step with answers kept; never after the flow has ended."""

from tests.flow import DETAILS_OK, ELIGIBILITY_OK, PREVALIDATION_OK, alert, start, submit, to_details


def action_ids(view):
    return [a["id"] for a in view["screen"]["actions"]]


def test_back_is_offered_on_eligibility_and_details_only(client):
    c, _ = client
    view = start(c)
    assert action_ids(view) == ["cancel", "continue"]
    view = submit(c, view, PREVALIDATION_OK)
    assert action_ids(view) == ["back", "cancel", "continue"]
    view = submit(c, view, ELIGIBILITY_OK)
    assert action_ids(view) == ["back", "cancel", "continue"]


def test_back_from_eligibility_shows_prevalidation_with_answers(client):
    c, _ = client
    view = submit(c, start(c), PREVALIDATION_OK)
    view = submit(c, view, {}, action="back")
    assert view["status"] == "active"
    assert view["screen"]["step"] == "prevalidation"
    assert view["screen"]["values"] == PREVALIDATION_OK
    assert view["screen"]["errors"] == {}
    assert view["completed_steps"] == []


def test_back_keeps_unfinished_input_without_validating(client):
    c, _ = client
    view = to_details(c)
    view = submit(c, view, {"serial_number": "12", "payee": "Jane Doe"}, action="back")
    assert view["screen"]["step"] == "eligibility"
    assert view["screen"]["values"] == ELIGIBILITY_OK
    assert view["screen"]["errors"] == {}

    view = submit(c, view, ELIGIBILITY_OK)
    assert view["screen"]["step"] == "check_details"
    assert view["screen"]["values"]["serial_number"] == "12"
    assert view["screen"]["values"]["payee"] == "Jane Doe"


def test_going_back_two_steps_and_forward_keeps_everything(client):
    c, container = client
    view = submit(c, to_details(c), DETAILS_OK, action="back")
    view = submit(c, view, {}, action="back")
    assert view["screen"]["step"] == "prevalidation"

    view = submit(c, view, view["screen"]["values"])
    view = submit(c, view, view["screen"]["values"])
    assert view["screen"]["values"] == DETAILS_OK
    view = submit(c, view, view["screen"]["values"])
    assert view["status"] == "completed"
    assert container.obcv.calls == 1


def test_changed_answer_after_back_is_checked_again(client):
    c, _ = client
    view = submit(c, to_details(c), {}, action="back")
    view = submit(c, view, {"presented": "yes", "account_type": "deposit"})
    assert view["status"] == "stopped"
    assert "deposit account" in alert(view)["message"]


def test_no_back_from_a_stop_screen(client):
    c, _ = client
    view = submit(c, start(c), PREVALIDATION_OK)
    view = submit(c, view, {"presented": "yes", "account_type": "deposit"})
    assert action_ids(view) == ["close"]
    again = submit(c, view, {}, action="back", step="stopped")
    assert again["status"] == "stopped"
    assert again["screen"]["step"] == "stopped"


def test_no_back_after_verification(client):
    c, container = client
    details = to_details(c)
    done = submit(c, details, DETAILS_OK)
    again = submit(c, details, {}, action="back", step="check_details")
    assert again == done
    assert container.obcv.calls == 1


def test_back_on_first_step_stays_put(client):
    c, _ = client
    view = submit(c, start(c), {"identity_verified": True}, action="back")
    assert view["screen"]["step"] == "prevalidation"
    assert view["screen"]["values"]["identity_verified"] is True


def test_back_is_in_the_audit_trail(client):
    c, container = client
    view = submit(c, start(c), PREVALIDATION_OK)
    view = submit(c, view, {}, action="back")
    events = container.store.get(view["session_id"])["events"]
    assert {"type": "went_back", "step": "eligibility"}.items() <= events[-1].items()
