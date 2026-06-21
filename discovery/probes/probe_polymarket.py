from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

from _common import ROOT, USER_AGENT, now_utc_iso, save_sample


SOURCE_ID = "polymarket"
GAMMA_BASE = "https://gamma-api.polymarket.com"
FINDINGS_DIR = ROOT / "discovery" / "findings"
WORLD_CUP_TAG_ID = "102232"
EVENT_PAGE_LIMIT = 100
PRICE_SUM_TOLERANCE = 0.02


def api_get(client: httpx.Client, path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{GAMMA_BASE}{path}"
    response = client.get(url, params=params or {})
    facts = {
        "url": str(response.url),
        "status_code": response.status_code,
        "content_type": response.headers.get("content-type"),
        "bytes": len(response.content),
    }
    if response.status_code != 200:
        preview = response.text[:300].replace("\n", " ")
        raise RuntimeError(f"GET {response.url} returned HTTP {response.status_code}: {preview}")

    content_type = response.headers.get("content-type", "").lower()
    if "application/json" not in content_type:
        preview = response.text[:300].replace("\n", " ")
        raise RuntimeError(
            f"GET {response.url} returned HTTP 200 but non-JSON content-type "
            f"{content_type!r}: {preview}"
        )

    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        preview = response.text[:300].replace("\n", " ")
        raise RuntimeError(f"GET {response.url} returned invalid JSON: {preview}") from exc

    return payload, facts


def require_shape(payload: Any, expected: type, url: str) -> None:
    if not isinstance(payload, expected):
        raise RuntimeError(
            f"GET {url} returned JSON {type(payload).__name__}, expected {expected.__name__}"
        )


def parse_array(value: Any) -> list[Any] | None:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, list) else None
    return None


def parse_outcome_prices(market: dict[str, Any]) -> dict[str, Any]:
    outcomes = parse_array(market.get("outcomes"))
    prices_raw = parse_array(market.get("outcomePrices"))
    result: dict[str, Any] = {
        "market_id": market.get("id"),
        "question": market.get("question"),
        "has_outcomes": outcomes is not None,
        "has_outcome_prices": prices_raw is not None,
        "valid": False,
    }
    if outcomes is None or prices_raw is None:
        return result
    if len(outcomes) != len(prices_raw):
        result["length_mismatch"] = {"outcomes": len(outcomes), "outcomePrices": len(prices_raw)}
        return result

    prices: list[float] = []
    for raw in prices_raw:
        try:
            prices.append(float(raw))
        except (TypeError, ValueError):
            result["non_numeric_price"] = raw
            return result

    price_sum = sum(prices)
    result.update(
        {
            "valid": True,
            "outcome_count": len(outcomes),
            "price_sum": price_sum,
            "sum_within_tolerance": abs(price_sum - 1.0) <= PRICE_SUM_TOLERANCE,
            "outcomes": outcomes,
            "prices": prices,
        }
    )
    return result


def yes_probability(market: dict[str, Any]) -> float | None:
    parsed = parse_outcome_prices(market)
    if not parsed.get("valid"):
        return None
    outcomes = parsed["outcomes"]
    prices = parsed["prices"]
    for index, outcome in enumerate(outcomes):
        if str(outcome).lower() == "yes":
            return float(prices[index])
    return float(prices[0]) if prices else None


def market_liquidity(market: dict[str, Any]) -> float | None:
    for key in ("liquidity", "liquidityNum", "liquidityClob"):
        value = market.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def event_liquidity(event: dict[str, Any]) -> float | None:
    for key in ("liquidity", "liquidityClob"):
        value = event.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def event_volume(event: dict[str, Any]) -> float | None:
    value = event.get("volume")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def classify_event(event: dict[str, Any]) -> set[str]:
    title = str(event.get("title") or "").lower()
    markets = event.get("markets") or []
    labels: set[str] = set()
    if title.strip() == "world cup winner":
        labels.add("outright_tournament_winner")
    if " vs. " in title or " vs " in title:
        if " - exact score" in title:
            labels.add("exact_scorelines")
        elif " - " in title or len(markets) != 3:
            labels.add("individual_match_props")
        else:
            labels.add("individual_match_results")
    if ("group" in title and ("winner" in title or "advance" in title)) or (
        "advance to knockout" in title
    ):
        labels.add("group_winners_advancement")
    if "exact score" in title:
        labels.add("exact_scorelines")
    return labels


def classify_market(market: dict[str, Any]) -> set[str]:
    question = str(market.get("question") or "").lower()
    slug = str(market.get("slug") or "").lower()
    labels: set[str] = set()
    if "exact score" in question or slug.startswith("exact-score"):
        labels.add("exact_scorelines")
    if "advance to the knockout" in question or "win group" in question:
        labels.add("group_winners_advancement")
    return labels


def compact_market(market: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": market.get("id"),
        "question": market.get("question"),
        "outcomes": market.get("outcomes"),
        "outcomePrices": market.get("outcomePrices"),
        "volume": market.get("volume"),
        "volumeNum": market.get("volumeNum"),
        "liquidity": market.get("liquidity"),
        "liquidityNum": market.get("liquidityNum"),
        "liquidityClob": market.get("liquidityClob"),
        "bestBid": market.get("bestBid"),
        "bestAsk": market.get("bestAsk"),
        "lastTradePrice": market.get("lastTradePrice"),
        "enableOrderBook": market.get("enableOrderBook"),
        "acceptingOrders": market.get("acceptingOrders"),
    }


def compact_event(event: dict[str, Any], market_limit: int = 8) -> dict[str, Any]:
    markets = event.get("markets") or []
    return {
        "id": event.get("id"),
        "title": event.get("title"),
        "slug": event.get("slug"),
        "active": event.get("active"),
        "closed": event.get("closed"),
        "endDate": event.get("endDate"),
        "volume": event.get("volume"),
        "liquidity": event.get("liquidity"),
        "liquidityClob": event.get("liquidityClob"),
        "openInterest": event.get("openInterest"),
        "enableOrderBook": event.get("enableOrderBook"),
        "negRisk": event.get("negRisk"),
        "market_count": len(markets),
        "markets": [compact_market(market) for market in markets[:market_limit]],
    }


def write_json(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path.relative_to(ROOT).as_posix()


def fetch_world_cup_events(client: httpx.Client) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    request_facts: list[dict[str, Any]] = []
    offset = 0
    while True:
        params = {
            "tag_id": WORLD_CUP_TAG_ID,
            "limit": EVENT_PAGE_LIMIT,
            "offset": offset,
            "active": "true",
            "closed": "false",
            "order": "volume",
            "ascending": "false",
        }
        payload, facts = api_get(client, "/events", params)
        require_shape(payload, list, facts["url"])
        request_facts.append({**facts, "event_count": len(payload)})
        if not payload:
            break
        events.extend(payload)
        if len(payload) < EVENT_PAGE_LIMIT:
            break
        offset += EVENT_PAGE_LIMIT
    return events, request_facts


def public_search(client: httpx.Client, query: str) -> dict[str, Any]:
    payload, facts = api_get(client, "/public-search", {"q": query})
    require_shape(payload, dict, facts["url"])
    if "events" not in payload or "pagination" not in payload:
        raise RuntimeError(f"GET {facts['url']} returned JSON without events/pagination keys")
    events = payload["events"]
    if not isinstance(events, list):
        raise RuntimeError(f"GET {facts['url']} returned non-list events")
    return {
        "query": query,
        "request": facts,
        "returned_events": len(events),
        "pagination": payload.get("pagination"),
        "top_events": [compact_event(event, market_limit=3) for event in events[:5]],
    }


def summarize(events: list[dict[str, Any]]) -> dict[str, Any]:
    all_markets = [
        market
        for event in events
        for market in (event.get("markets") or [])
        if isinstance(market, dict)
    ]
    price_checks = [parse_outcome_prices(market) for market in all_markets]
    valid_checks = [check for check in price_checks if check.get("valid")]
    invalid_checks = [check for check in price_checks if not check.get("valid")]
    sums = [float(check["price_sum"]) for check in valid_checks]

    coverage: dict[str, dict[str, Any]] = {
        "outright_tournament_winner": {"events": {}, "market_ids": set()},
        "individual_match_results": {"events": {}, "market_ids": set()},
        "individual_match_props": {"events": {}, "market_ids": set()},
        "group_winners_advancement": {"events": {}, "market_ids": set()},
        "exact_scorelines": {"events": {}, "market_ids": set()},
    }
    for event in events:
        event_labels = classify_event(event)
        markets = event.get("markets") or []
        for label in event_labels:
            coverage[label]["events"][event.get("id")] = compact_event(event, market_limit=3)
            for market in markets:
                coverage[label]["market_ids"].add(market.get("id"))
        for market in markets:
            for label in classify_market(market):
                if label not in coverage:
                    continue
                coverage[label]["market_ids"].add(market.get("id"))
                coverage[label]["events"][event.get("id")] = compact_event(event, market_limit=3)

    coverage_summary: dict[str, Any] = {}
    for label, data in coverage.items():
        event_samples = list(data["events"].values())
        coverage_summary[label] = {
            "exists": bool(event_samples or data["market_ids"]),
            "event_count": len(event_samples),
            "market_count": len(data["market_ids"]),
            "sample_events": event_samples[:5],
        }

    representative_events: dict[str, Any] = {}
    for key, title_fragment in {
        "outright": "world cup winner",
        "match_result": " vs. ",
        "advancement": "advance to knockout",
        "group_winner": "group",
        "exact_score": "more markets",
    }.items():
        for event in events:
            title = str(event.get("title") or "").lower()
            if title_fragment in title:
                representative_events[key] = compact_event(event, market_limit=5)
                break

    event_yes_sums: list[dict[str, Any]] = []
    for event in events:
        markets = event.get("markets") or []
        yes_prices = [yes_probability(market) for market in markets]
        yes_prices = [price for price in yes_prices if price is not None]
        if len(yes_prices) < 2:
            continue
        event_yes_sums.append(
            {
                "event_id": event.get("id"),
                "title": event.get("title"),
                "market_count": len(markets),
                "priced_yes_count": len(yes_prices),
                "yes_price_sum": round(sum(yes_prices), 6),
                "volume": event_volume(event),
                "liquidity": event_liquidity(event),
            }
        )
    event_yes_sums.sort(key=lambda item: float(item.get("volume") or 0), reverse=True)

    liquidity_values = [value for value in (event_liquidity(event) for event in events) if value is not None]
    volume_values = [value for value in (event_volume(event) for event in events) if value is not None]

    return {
        "event_count": len(events),
        "market_count": len(all_markets),
        "coverage": coverage_summary,
        "outcomes_shape": {
            "markets_with_valid_numeric_outcome_prices": len(valid_checks),
            "markets_missing_or_invalid_outcome_prices": len(invalid_checks),
            "markets_price_sum_within_0_02_of_1": sum(
                1 for check in valid_checks if check.get("sum_within_tolerance")
            ),
            "price_sum_min": min(sums) if sums else None,
            "price_sum_max": max(sums) if sums else None,
            "invalid_examples": invalid_checks[:8],
            "valid_examples": valid_checks[:5],
        },
        "event_level_yes_price_sums_top_volume": event_yes_sums[:10],
        "liquidity_volume_fields": {
            "event_volume_min": min(volume_values) if volume_values else None,
            "event_volume_max": max(volume_values) if volume_values else None,
            "event_liquidity_min": min(liquidity_values) if liquidity_values else None,
            "event_liquidity_max": max(liquidity_values) if liquidity_values else None,
            "fields_seen_on_events": sorted(
                {
                    key
                    for event in events
                    for key in event.keys()
                    if "volume" in key.lower() or "liquidity" in key.lower() or key == "openInterest"
                }
            ),
            "fields_seen_on_markets": sorted(
                {
                    key
                    for market in all_markets
                    for key in market.keys()
                    if "volume" in key.lower() or "liquidity" in key.lower() or key == "openInterest"
                }
            ),
        },
        "representative_events": representative_events,
    }


def main() -> None:
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    with httpx.Client(headers=headers, timeout=60.0, follow_redirects=True) as client:
        sports, sports_request = api_get(client, "/sports")
        require_shape(sports, list, sports_request["url"])
        fifwc_sports = [sport for sport in sports if str(sport.get("sport")) == "fifwc"]
        if not fifwc_sports:
            raise RuntimeError("Could not find fifwc sports metadata in Gamma /sports response")

        search_world_cup = public_search(client, "World Cup")
        search_fifa = public_search(client, "FIFA")
        events, event_requests = fetch_world_cup_events(client)
        if not events:
            raise RuntimeError("No active open events returned for FIFA World Cup tag_id=102232")

    top_event = events[0]
    raw_sample = save_sample(
        SOURCE_ID,
        "sample-event-world-cup-winner.json",
        json.dumps(top_event, indent=2, sort_keys=True).encode("utf-8"),
    )
    excerpt_path = write_json(
        FINDINGS_DIR / "d5-polymarket-event-excerpt.json",
        {
            "generated_at": now_utc_iso(),
            "source": "Polymarket Gamma API",
            "event_excerpt": compact_event(top_event, market_limit=8),
        },
    )

    summary = {
        "source_id": SOURCE_ID,
        "generated_at": now_utc_iso(),
        "requires_secret": False,
        "documentation": {
            "market_data_overview": "https://docs.polymarket.com/market-data/overview",
            "fetching_markets": "https://docs.polymarket.com/market-data/fetching-markets",
        },
        "sports_metadata": {
            "request": sports_request,
            "fifwc": fifwc_sports,
            "selected_tag_id": WORLD_CUP_TAG_ID,
        },
        "search_cross_checks": [search_world_cup, search_fifa],
        "event_requests": event_requests,
        "sample_saved_at": raw_sample,
        "committed_excerpt_path": excerpt_path,
        **summarize(events),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
