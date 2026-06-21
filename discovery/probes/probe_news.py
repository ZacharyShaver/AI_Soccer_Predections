from __future__ import annotations

import json
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlencode

from _common import ROOT, http_get, now_utc_iso, save_sample


FINDINGS_DIR = ROOT / "discovery" / "findings"


def text_of(parent: ET.Element, name: str) -> str | None:
    child = parent.find(name)
    if child is None or child.text is None:
        return None
    return child.text.strip()


def main() -> int:
    query = '"soccer injury"'
    params = {
        "query": query,
        "mode": "artlist",
        "maxrecords": "3",
        "timespan": "1day",
        "sort": "datedesc",
        "format": "rssarchive",
    }
    url = "https://api.gdeltproject.org/api/v2/doc/doc?" + urlencode(params)

    # GDELT asks clients to keep requests at least 5 seconds apart.
    time.sleep(6)
    response = http_get(url)
    content_type = response.headers.get("content-type", "")
    body = response.content
    body_start = body[:200].lstrip().lower()
    if "xml" not in content_type.lower() and not body_start.startswith((b"<?xml", b"<rss")):
        raise RuntimeError(
            f"GDELT RSS probe returned non-XML content-type/shape: {content_type!r}"
        )

    root = ET.fromstring(body)
    if root.tag.lower() != "rss":
        raise RuntimeError(f"GDELT RSS probe returned XML but not RSS: root={root.tag!r}")

    channel = root.find("channel")
    if channel is None:
        raise RuntimeError("GDELT RSS probe returned RSS without a channel element")

    items = channel.findall("item")
    schema_fields = sorted({child.tag for item in items for child in list(item)})
    excerpt = {
        "source": "GDELT DOC 2.0 API RSS archive",
        "fetched_at": now_utc_iso(),
        "query_url": url,
        "content_type": content_type,
        "rss_root": root.tag,
        "item_count": len(items),
        "schema_fields_observed": schema_fields,
        "items": [
            {
                "title": text_of(item, "title"),
                "link": text_of(item, "link"),
                "pubDate": text_of(item, "pubDate"),
                "guid": text_of(item, "guid"),
            }
            for item in items[:5]
        ],
        "body_fields_excluded": ["description", "content:encoded"],
    }

    raw_sample = save_sample("news", "gdelt-doc-rss-sample.xml", body)
    excerpt["raw_sample"] = raw_sample

    FINDINGS_DIR.mkdir(parents=True, exist_ok=True)
    excerpt_path = FINDINGS_DIR / "d9-news-gdelt-excerpt.json"
    excerpt_path.write_text(json.dumps(excerpt, indent=2, ensure_ascii=True) + "\n")
    print(json.dumps({"excerpt": excerpt_path.relative_to(ROOT).as_posix(), **excerpt}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
