import pytest
from mcp.a2a_mcp.server import (
    send, list_inbox, consume, ttl_decrement, cycle_check,
)


def test_send_and_receive(tmp_lacakin):
    chain_id = send(case_id="c1", from_agent="mata", to_agent="cadang",
                    reason="motor menuju selatan", payload={"area": "Buah Batu"})
    assert isinstance(chain_id, str) and len(chain_id) > 0
    msgs = list_inbox(to_agent="cadang")
    assert len(msgs) == 1
    assert msgs[0]["from_agent"] == "mata"
    assert msgs[0]["reason"] == "motor menuju selatan"
    assert msgs[0]["ttl_ticks"] == 2  # default TTL


def test_consume_marks_delivered(tmp_lacakin):
    send(case_id="c1", from_agent="mata", to_agent="cadang", reason="x", payload={})
    msgs = list_inbox(to_agent="cadang")
    consume(message_ids=[msgs[0]["id"]])
    assert list_inbox(to_agent="cadang") == []


def test_cycle_check_blocks_same_chain_to_origin(tmp_lacakin):
    chain_id = send(case_id="c1", from_agent="mata", to_agent="cadang",
                    reason="r", payload={})
    assert cycle_check(chain_id=chain_id, to_agent="mata") is True
    assert cycle_check(chain_id=chain_id, to_agent="pasar") is False


def test_ttl_decrements_and_expires(tmp_lacakin):
    send(case_id="c1", from_agent="mata", to_agent="cadang",
         reason="r", payload={}, ttl_ticks=1)
    msgs = list_inbox(to_agent="cadang")
    consume(message_ids=[msgs[0]["id"]])
    send(case_id="c1", from_agent="mata", to_agent="cadang",
         reason="r2", payload={}, ttl_ticks=2)
    ttl_decrement(to_agent="cadang")
    msgs = list_inbox(to_agent="cadang")
    assert msgs[0]["ttl_ticks"] == 1
    ttl_decrement(to_agent="cadang")
    assert list_inbox(to_agent="cadang") == []
