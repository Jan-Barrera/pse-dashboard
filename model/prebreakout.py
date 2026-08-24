import datetime
import logging
import os

import pandas as pd
import sqlalchemy as sa

from db.hist_data import engine
from model.swingtrade import fetch_company_names, format_peso

logger = logging.getLogger(__name__)

CACHE_DIR = "./data/temp"
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_PATH = os.path.join(CACHE_DIR, "prebreakout_latest.csv")

REQUIRED_COLUMNS = {"symbol", "date", "status", "close", "source", "note"}
WATCHLIST_COLUMNS = [
    "Symbol",
    "Company Name",
    "Date",
    "Close",
    "Status",
    "Source",
    "Note",
]


def expected_latest_data_date(today: datetime.date | None = None) -> datetime.date:
    """Prices lag by 1 session; expect data through the prior trading day."""
    day = (today or datetime.date.today()) - datetime.timedelta(days=1)
    while day.weekday() >= 5:
        day -= datetime.timedelta(days=1)
    return day


def load_cached_prebreakout(path: str = CACHE_PATH) -> pd.DataFrame | None:
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return None
    try:
        cached = pd.read_csv(path, parse_dates=["date"])
    except (pd.errors.EmptyDataError, ValueError, KeyError):
        return None
    if cached.empty or not REQUIRED_COLUMNS.issubset(cached.columns):
        return None

    last_date = pd.to_datetime(cached["date"]).max().date()
    mtime_date = datetime.date.fromtimestamp(os.path.getmtime(path))
    if last_date >= expected_latest_data_date() or mtime_date >= datetime.date.today():
        logger.info(
            "Using cached prebreakout through %s (%s rows): %s",
            last_date,
            len(cached),
            path,
        )
        return cached

    logger.info("Cached prebreakout ends %s; fetching latest from Supabase...", last_date)
    return None


def fetch_latest_prebreakout(db_engine: sa.Engine) -> pd.DataFrame:
    query = sa.text(
        """
        select symbol, date, status, close, source, note
        from prebreakout_results
        where date = (select max(date) from prebreakout_results)
        order by symbol
        """
    )
    df = pd.read_sql(query, db_engine, parse_dates=["date"])
    if df.empty:
        raise ValueError("Supabase table prebreakout_results returned no rows")
    return df


def get_prebreakout_dataframe() -> pd.DataFrame:
    """Return the latest prebreakout rows from cache or Supabase."""
    df = load_cached_prebreakout()
    if df is None:
        df = fetch_latest_prebreakout(engine)
        df.to_csv(CACHE_PATH, index=False)
        logger.info(
            "Fetched and cached: %s (%s rows through %s)",
            CACHE_PATH,
            len(df),
            df["date"].max().date(),
        )
    return df


def get_prebreakout_watchlist() -> pd.DataFrame:
    """Return pre-breakout watchlist formatted for the UI table."""
    df = get_prebreakout_dataframe()
    if df.empty:
        return pd.DataFrame(columns=WATCHLIST_COLUMNS)

    companies = fetch_company_names(engine, df["symbol"].tolist())
    rows = []
    for _, row in df.iterrows():
        symbol = row["symbol"]
        trade_date = row["date"]
        date_label = (
            pd.Timestamp(trade_date).strftime("%Y-%m-%d")
            if pd.notna(trade_date)
            else ""
        )
        rows.append(
            {
                "Symbol": symbol,
                "Company Name": companies.get(symbol, ""),
                "Date": date_label,
                "Close": format_peso(row["close"]),
                "Status": row.get("status") or "",
                "Source": row.get("source") or "",
                "Note": row.get("note") or "",
            }
        )

    return pd.DataFrame(rows, columns=WATCHLIST_COLUMNS)
