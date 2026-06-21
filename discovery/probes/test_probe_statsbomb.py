from __future__ import annotations

import importlib.util
from pathlib import Path

import httpx
import pytest


def load_probe_module():
    path = Path(__file__).with_name("probe_statsbomb.py")
    assert path.exists(), "probe_statsbomb.py should exist"
    spec = importlib.util.spec_from_file_location("probe_statsbomb", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_response(content_type: str, content: bytes) -> httpx.Response:
    return httpx.Response(
        200,
        headers={"content-type": content_type},
        content=content,
        request=httpx.Request("GET", "https://example.test/statsbomb.json"),
    )


def test_parse_json_response_rejects_http_200_with_non_json_content_type():
    module = load_probe_module()
    response = make_response("text/html; charset=utf-8", b"<html>not json</html>")

    with pytest.raises(RuntimeError, match="non-JSON content-type"):
        module.parse_json_response(response, "competitions.json")


def test_require_list_of_dicts_rejects_wrong_json_shape():
    module = load_probe_module()
    response = make_response("application/json", b'{"not": "a list"}')
    payload = module.parse_json_response(response, "competitions.json")

    with pytest.raises(RuntimeError, match="expected list"):
        module.require_list_of_dicts(payload, "competitions.json")
