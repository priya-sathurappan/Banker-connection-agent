"""Behaviour across datacenters: two app instances sharing one MongoDB database
stand in for two datacenters behind a load balancer without sticky sessions."""

from concurrent.futures import ThreadPoolExecutor

from app.tools.obcv import MockObcvClient
from tests.flow import DETAILS_OK, ELIGIBILITY_OK, PREVALIDATION_OK, start, submit


def test_session_continues_in_another_datacenter(make_client, mongo_db):
    dc_a, _ = make_client("mongo", mongo_db, datacenter="dc-a")
    dc_b, container_b = make_client("mongo", mongo_db, datacenter="dc-b")

    view = start(dc_a)
    view = submit(dc_b, view, PREVALIDATION_OK)
    view = submit(dc_a, view, ELIGIBILITY_OK)
    view = submit(dc_b, view, DETAILS_OK)

    assert view["status"] == "completed"
    record = container_b.store.get(view["session_id"])
    assert record["last_dc"] == "dc-b"
    assert {e["dc"] for e in record["events"]} == {"dc-a", "dc-b"}


def test_concurrent_submits_in_two_datacenters_call_obcv_once(make_client, mongo_db):
    obcv = MockObcvClient(delay_ms=500)
    dc_a, _ = make_client("mongo", mongo_db, datacenter="dc-a", obcv=obcv)
    dc_b, _ = make_client("mongo", mongo_db, datacenter="dc-b", obcv=obcv)

    view = start(dc_a)
    view = submit(dc_a, view, PREVALIDATION_OK)
    view = submit(dc_a, view, ELIGIBILITY_OK)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda c: submit(c, view, DETAILS_OK), [dc_a, dc_b]))

    assert obcv.calls == 1
    assert [r["status"] for r in results] == ["completed", "completed"]
    assert results[0]["screen"]["blocks"][1] == results[1]["screen"]["blocks"][1]
