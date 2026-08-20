from __future__ import annotations

import html
import json
import logging
import re
import threading
import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import requests

PSE_HOME_URL = "https://www.pse.com.ph/"
PSE_COMPOSITE_URL = "https://www.pse.com.ph/composite-sector-indices/"
PSE_AJAX_URL = "https://www.pse.com.ph/wp-admin/admin-ajax.php"
PTP_AJAX_ACTION = "ptp_load_posts"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
PSE_AJAX_HEADERS = {
    "Referer": PSE_HOME_URL,
    "Origin": "https://www.pse.com.ph",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}
PSE_HOME_RETRY_ATTEMPTS = 3
INDEX_CODES = ("PSEI", "ALL", "FIN", "IND")
INDEX_DISPLAY_NAMES = {
    "PSEI": "PSEi INDEX",
    "ALL": "ALL SHARES INDEX",
    "FIN": "FINANCIALS INDEX",
    "IND": "INDUSTRIALS INDEX",
}
SCRAPE_INTERVAL_SECONDS = 15 * 60
_indices_cache: tuple[float, list[dict[str, Any]]] | None = None
_news_cache: tuple[float, list[tuple[str, str, str]]] | None = None
_pse_home_cache: tuple[float, requests.Session, str] | None = None
_pse_home_lock = threading.Lock()

logger = logging.getLogger(__name__)


def _fallback_indices() -> list[dict[str, Any]]:
    return [
        {
            "name": "PSEi INDEX",
            "value": "6,629.15",
            "change": "+68.35 (+1.04%)",
            "up": True,
            "value_b": "₱6.28B",
            "vol": "1.18B",
            "trades": "96,845",
        },
        {
            "name": "ALL SHARES INDEX",
            "value": "3,558.45",
            "change": "+32.24 (+0.91%)",
            "up": True,
            "value_b": "₱3.88B",
            "vol": "703.45M",
            "trades": "67,125",
        },
        {
            "name": "FINANCIALS INDEX",
            "value": "1,988.36",
            "change": "+14.88 (+0.75%)",
            "up": True,
            "value_b": None,
            "vol": None,
            "trades": None,
        },
        {
            "name": "INDUSTRIALS INDEX",
            "value": "9,321.28",
            "change": "+115.47 (+1.25%)",
            "up": True,
            "value_b": None,
            "vol": None,
            "trades": None,
        },
    ]


def _extract_iframe_src(page_html: str, pattern: str) -> str | None:
    match = re.search(
        rf'<iframe[^>]+(?:src|data-opt-src)=["\']([^"\']*{pattern}[^"\']*)["\']',
        page_html,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    src = html.unescape(match.group(1))
    if src == "about:blank":
        return None
    if src.startswith("//"):
        return f"https:{src}"
    if src.startswith("/"):
        return f"https://frames.pse.com.ph{src}"
    return src


def _format_index_value(raw_value: str) -> str:
    value = float(raw_value)
    return f"{value:,.2f}"


def _format_change(change: str, percent_change: str) -> tuple[str, bool]:
    change_value = float(change)
    percent_value = float(percent_change)
    sign = "+" if change_value >= 0 else ""
    change_text = f"{sign}{change_value:,.2f} ({sign}{percent_value:.2f}%)"
    return change_text, change_value >= 0


def _format_peso_value(raw_value: str) -> str:
    value = float(raw_value.replace(",", ""))
    if value >= 1_000_000_000:
        return f"₱{value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"₱{value / 1_000_000:.2f}M"
    return f"₱{value:,.2f}"


def _format_volume(raw_value: str) -> str:
    value = float(raw_value.replace(",", ""))
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    return f"{value:,.0f}"


def _format_trades(raw_value: str) -> str:
    return f"{int(float(raw_value.replace(',', ''))):,}"


def _parse_market_summary(frame_html: str) -> dict[str, str | None]:
    labels = {
        "value_b": r"Total Value \(in PHP\)",
        "vol": r"Total Volume",
        "trades": r"Total Trades",
    }
    summary: dict[str, str | None] = {"value_b": None, "vol": None, "trades": None}
    for key, label in labels.items():
        match = re.search(
            rf"<td[^>]*>{label}</td>\s*<td[^>]*>([^<]+)</td>",
            frame_html,
            flags=re.IGNORECASE,
        )
        if not match:
            continue
        raw_value = html.unescape(match.group(1)).strip()
        if key == "value_b":
            summary[key] = _format_peso_value(raw_value)
        elif key == "vol":
            summary[key] = _format_volume(raw_value)
        else:
            summary[key] = _format_trades(raw_value)
    return summary


def _parse_index_payload(frame_html: str, code: str) -> dict[str, Any]:
    match = re.search(
        rf'id="{code}-key"[^>]*value="([^"]+)"',
        frame_html,
        flags=re.IGNORECASE,
    )
    if not match:
        raise ValueError(f"Missing index payload for {code}")
    return json.loads(html.unescape(match.group(1)))


def _scrape_indices() -> list[dict[str, Any]]:
    session, home_html = _get_pse_home_context()

    composite_response = session.get(PSE_COMPOSITE_URL, timeout=30)
    composite_response.raise_for_status()

    frame_url = (
        _extract_iframe_src(composite_response.text, r"frames\.pse\.com\.ph/compositeSector")
        or _extract_iframe_src(home_html, r"frames\.pse\.com\.ph")
        or "https://frames.pse.com.ph/compositeSector"
    )

    frame_response = session.get(frame_url, timeout=30)
    frame_response.raise_for_status()
    frame_html = frame_response.text

    market_summary = _parse_market_summary(frame_html)
    indices: list[dict[str, Any]] = []

    for code in INDEX_CODES:
        payload = _parse_index_payload(frame_html, code)
        change_text, is_up = _format_change(payload["Change"], payload["PercentChange"])
        entry: dict[str, Any] = {
            "name": INDEX_DISPLAY_NAMES[code],
            "value": _format_index_value(payload["Value"]),
            "change": change_text,
            "up": is_up,
            "value_b": None,
            "vol": None,
            "trades": None,
        }
        if code == "PSEI":
            entry.update(market_summary)
        indices.append(entry)

    return indices


def _strip_html(raw: str) -> str:
    text = re.sub(r"<[^>]+>", "", raw)
    return html.unescape(re.sub(r"\s+", " ", text)).strip()


def _parse_press_title_html(title_html: str) -> tuple[str, str]:
    match = re.search(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        title_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return _strip_html(title_html), ""
    url = html.unescape(match.group(1)).strip()
    title = _strip_html(match.group(2))
    return title, url


def _find_press_room_table_id(page_html: str) -> str | None:
    for match in re.finditer(
        r'<table id="(ptp_[^"]+)" class="posts-data-table"[^>]*data-config="([^"]+)"',
        page_html,
    ):
        config = json.loads(html.unescape(match.group(2)))
        column_classes = [
            column.get("className")
            for column in config.get("columnDefs", [])
        ]
        if (
            column_classes
            and column_classes[0] == "col-title"
            and "col-date" in column_classes
        ):
            return match.group(1)

    return None


def _pse_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    return session


def _fetch_pse_homepage(session: requests.Session) -> str:
    last_response: requests.Response | None = None
    for attempt in range(1, PSE_HOME_RETRY_ATTEMPTS + 1):
        response = session.get(PSE_HOME_URL, timeout=30)
        last_response = response
        if response.status_code == 200:
            return response.text
        if response.status_code == 403 and attempt < PSE_HOME_RETRY_ATTEMPTS:
            logger.warning(
                "PSE homepage returned 403 (attempt %s/%s)",
                attempt,
                PSE_HOME_RETRY_ATTEMPTS,
            )
            time.sleep(attempt)
            continue
        response.raise_for_status()

    if last_response is not None:
        last_response.raise_for_status()
    raise requests.RequestException(f"Failed to fetch PSE homepage from {PSE_HOME_URL}")


def _get_pse_home_context() -> tuple[requests.Session, str]:
    global _pse_home_cache

    now = time.time()
    if _pse_home_cache and now - _pse_home_cache[0] < SCRAPE_INTERVAL_SECONDS:
        return _pse_home_cache[1], _pse_home_cache[2]

    with _pse_home_lock:
        now = time.time()
        if _pse_home_cache and now - _pse_home_cache[0] < SCRAPE_INTERVAL_SECONDS:
            return _pse_home_cache[1], _pse_home_cache[2]

        session = _pse_session()
        home_html = _fetch_pse_homepage(session)
        _pse_home_cache = (now, session, home_html)
        return session, home_html


def _load_press_room_posts(
    session: requests.Session,
    table_id: str,
    limit: int,
) -> list[tuple[str, str, str]]:
    ajax_response = session.post(
        PSE_AJAX_URL,
        data={"action": PTP_AJAX_ACTION, "table_id": table_id},
        headers=PSE_AJAX_HEADERS,
        timeout=30,
    )
    ajax_response.raise_for_status()

    try:
        payload = ajax_response.json()
    except json.JSONDecodeError as exc:
        raise ValueError("Press Room AJAX returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise ValueError("Press Room AJAX returned an unexpected payload")

    news: list[tuple[str, str, str]] = []
    for row in payload.get("data", []):
        if not isinstance(row, dict):
            continue
        title_html = row.get("title")
        raw_date = row.get("date")
        if not title_html or not raw_date:
            continue
        title, url = _parse_press_title_html(title_html)
        if not title:
            continue
        news.append((raw_date, title, url))
        if len(news) >= limit:
            break

    if not news:
        raise ValueError("No Press Room posts returned from PSE")

    return news


def _scrape_press_room(limit: int = 10) -> list[tuple[str, str, str]]:
    session, home_html = _get_pse_home_context()

    table_id = _find_press_room_table_id(home_html)
    if not table_id:
        raise ValueError("Press Room table not found on PSE homepage")

    news = _load_press_room_posts(session, table_id, limit)
    logger.info("Loaded %s Press Room posts from PSE homepage", len(news))
    return news


def get_indices() -> list[dict[str, Any]]:
    global _indices_cache

    now = time.time()
    if _indices_cache and now - _indices_cache[0] < SCRAPE_INTERVAL_SECONDS:
        return _indices_cache[1]

    try:
        indices = _scrape_indices()
    except (requests.RequestException, ValueError, KeyError, json.JSONDecodeError):
        indices = _fallback_indices()

    _indices_cache = (now, indices)
    return indices


def get_indices_updated_at() -> datetime | None:
    if _indices_cache is None:
        return None
    return datetime.fromtimestamp(_indices_cache[0], tz=ZoneInfo("Asia/Manila"))


def indices_needs_refresh() -> bool:
    if _indices_cache is None:
        return True
    return time.time() - _indices_cache[0] >= SCRAPE_INTERVAL_SECONDS


def get_market_news() -> list[tuple[str, str, str]]:
    global _news_cache

    now = time.time()
    if _news_cache and now - _news_cache[0] < SCRAPE_INTERVAL_SECONDS:
        return _news_cache[1]

    try:
        news = _scrape_press_room()
    except (requests.RequestException, ValueError, KeyError, json.JSONDecodeError) as exc:
        logger.warning("Market news scrape failed: %s", exc)
        if _news_cache:
            return _news_cache[1]
        return []

    _news_cache = (now, news)
    return news


def market_news_needs_refresh() -> bool:
    if _news_cache is None:
        return True
    return time.time() - _news_cache[0] >= SCRAPE_INTERVAL_SECONDS


def get_market_breadth() -> dict:
    return {"advancers": 119, "decliners": 67, "unchanged": 41, "total": 227}


def get_watchlist_data() -> pd.DataFrame:
    rows = [
        ["1", "AEV", "Aboitiz Equity Ventures, Inc.", "Holdings", "₱61.20", "+2.35%", "5.21M", "3.64M", 61.3, "Uptrend", "₱58.50", "₱63.50", "Breakout above 60 · Strong volume, RSI up"],
        ["2", "JFC", "Jollibee Foods Corporation", "Consumer Discretionary", "₱236.00", "+1.72%", "2.31M", "1.78M", 58.7, "Uptrend", "₱225.00", "₱245.00", "Rebound from support · Bullish momentum"],
        ["3", "SM", "SM Investments Corporation", "Holdings", "₱972.00", "+1.46%", "1.65M", "1.32M", 55.9, "Uptrend", "₱940.00", "₱1,020.00", "Holding above 20 EMA · Buy on dips"],
        ["4", "ACEN", "ACEN Corporation", "Energy", "₱6.45", "+3.20%", "18.74M", "12.11M", 63.8, "Uptrend", "₱6.10", "₱6.80", "Breakout with volume · Trend continuation"],
        ["5", "ALI", "Ayala Land, Inc.", "Property", "₱32.10", "+1.91%", "6.82M", "4.97M", 59.4, "Uptrend", "₱30.50", "₱33.50", "Higher lows forming · Watch breakout"],
        ["6", "ICT", "International Container Terminal Services, Inc.", "Industrial", "₱395.00", "-0.25%", "1.02M", "1.25M", 48.6, "Sideways", "₱380.00", "₱410.00", "Consolidating range · Breakout watch"],
        ["7", "BPI", "Bank of the Philippine Islands", "Financials", "₱119.80", "+1.01%", "5.11M", "3.91M", 57.2, "Uptrend", "₱116.00", "₱123.00", "Bounce from support · Positive momentum"],
        ["8", "GLO", "Globe Telecom, Inc.", "Services", "₱1,870.00", "+1.36%", "1.23M", "1.05M", 56.1, "Uptrend", "₱1,800.00", "₱1,950.00", "Trend resumption · Strong volume"],
        ["9", "URC", "Universal Robina Corporation", "Consumer Staples", "₱135.40", "-0.37%", "2.77M", "2.31M", 45.2, "Sideways", "₱130.00", "₱138.00", "Range bound · Buy near support"],
        ["10", "DMC", "DMCI Holdings, Inc.", "Holdings", "₱11.80", "+2.61%", "9.24M", "6.47M", 62.7, "Uptrend", "₱11.20", "₱12.30", "Breakout above 11.50 · Strong buying interest"],
    ]
    columns = ["#", "Ticker", "Company", "Sector", "Last Price", "% Change", "Volume", "Avg Vol (20D)",
               "RSI (14)", "Trend", "Support", "Resistance", "Swing Setup / Notes"]
    return pd.DataFrame(rows, columns=columns)


def get_events() -> list[tuple[str, str, str]]:
    return [
        ("May 27", "PH", "Holiday: Memorial Day"),
        ("May 30", "US", "GDP (Q1) Preliminary"),
        ("May 31", "PH", "Inflation Rate (May)"),
    ]


def get_checklist_left() -> list[str]:
    return ["Trend is your friend", "Check support & resistance", "Confirm with volume"]


def get_checklist_right() -> list[str]:
    return ["Manage risk (set stop loss)", "Book partial profits", "Let winners run"]
