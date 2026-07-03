from unittest.mock import MagicMock

import pytest

from wc_predictor.lab.walkback.llm import LMClient


def _session_replying(*contents):
    session = MagicMock()
    responses = []
    for content in contents:
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"choices": [{"message": {"content": content}}]}
        responses.append(resp)
    session.post.side_effect = responses
    return session


def test_parses_plain_json():
    session = _session_replying('{"p_home": 0.5, "p_draw": 0.3, "p_away": 0.2}')
    out = LMClient(model="test").chat_json("sys", "user", session=session)
    assert out["p_home"] == 0.5


def test_parses_fenced_json_with_prose():
    content = 'Sure! Here is my forecast:\n```json\n{"pick": "home"}\n```\nGood luck!'
    session = _session_replying(content)
    assert LMClient(model="test").chat_json("s", "u", session=session)["pick"] == "home"


def test_retries_then_raises():
    session = _session_replying("not json", "still not json", "nope")
    with pytest.raises(ValueError):
        LMClient(model="test").chat_json("s", "u", max_retries=2, session=session)
    assert session.post.call_count == 3


def test_request_is_deterministic():
    session = _session_replying('{"a": 1}')
    LMClient(model="qwen2.5-14b-instruct").chat_json("s", "u", session=session)
    body = session.post.call_args.kwargs["json"]
    assert body["temperature"] == 0.0
    assert body["model"] == "qwen2.5-14b-instruct"
    assert body["messages"][0] == {"role": "system", "content": "s"}
