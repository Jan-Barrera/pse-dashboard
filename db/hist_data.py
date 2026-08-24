import datetime
import os
import logging
import pandas as pd
import sqlalchemy as sa
from dotenv import load_dotenv
from config import LOOKBACK_DAYS
import streamlit as st

load_dotenv()

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = st.secrets["DATABASE_URL"]
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL not found in .env or streamlit secrets")

engine = sa.create_engine(DATABASE_URL)

os.makedirs("./data/temp", exist_ok=True)


def clip_to_lookback(prices: pd.DataFrame, days: int = LOOKBACK_DAYS) -> pd.DataFrame:
    cutoff = prices.index.max() - pd.Timedelta(days=days)
    return prices[prices.index >= cutoff].copy()


def price_table_name(ticker: str) -> str:
    return f"price_{ticker.strip().lower()}"


def get_last_sync_date(db_engine: sa.Engine) -> datetime.date:
    """Return the latest completed market-data synchronization date."""
    with db_engine.connect() as conn:
        exists = conn.execute(
            sa.text(
                """
                select 1
                from information_schema.tables
                where table_schema = 'public'
                  and table_name = 'last_sync_time'
                """
            )
        ).scalar()
        if not exists:
            raise ValueError("Supabase table 'last_sync_time' was not found")
        latest = conn.execute(
            sa.text("select max(last_sync_date) from last_sync_time")
        ).scalar()
    if latest is None:
        raise ValueError("Supabase table 'last_sync_time' has no sync date")
    if isinstance(latest, datetime.datetime):
        return latest.date()
    return latest


def clear_cache(path: str) -> None:
    """Delete a stale or invalid price cache."""
    try:
        os.remove(path)
        logger.info("Cleared stale cache: %s", path)
    except FileNotFoundError:
        pass


def load_cached(
    path: str, *, last_sync_date: datetime.date
) -> pd.DataFrame | None:
    if not os.path.exists(path):
        return None
    if os.path.getsize(path) == 0:
        clear_cache(path)
        return None

    cache_date = datetime.date.fromtimestamp(os.path.getmtime(path))
    if cache_date < last_sync_date:
        logger.info(
            "Cache was refreshed %s (last sync %s); clearing and downloading new data...",
            cache_date,
            last_sync_date,
        )
        clear_cache(path)
        return None

    try:
        cached = pd.read_csv(path, parse_dates=["date"], index_col="date")
    except (pd.errors.EmptyDataError, ValueError, KeyError):
        clear_cache(path)
        return None
    required = {"Open", "High", "Low", "Close", "Volume"}
    if cached.empty or not required.issubset(cached.columns):
        clear_cache(path)
        return None
    cached = cached[~cached.index.duplicated(keep="last")].sort_index()
    last_date = cached.index.max().date()

    cached = clip_to_lookback(cached)
    logger.info(
        "Using cache refreshed %s after sync %s (trades through %s, %s rows, %sd): %s",
        cache_date,
        last_sync_date,
        last_date,
        len(cached),
        LOOKBACK_DAYS,
        path,
    )
    return cached


def load_price(db_engine: sa.Engine, ticker: str, days: int = LOOKBACK_DAYS) -> pd.DataFrame:
    """Load last `days` of OHLC from Supabase `price_{symbol}`."""
    table = price_table_name(ticker)
    with db_engine.connect() as conn:
        exists = conn.execute(
            sa.text(
                """
                select 1
                from information_schema.tables
                where table_schema = 'public'
                  and table_name = :table_name
                """
            ),
            {"table_name": table},
        ).scalar()
    if not exists:
        raise ValueError(f"No Supabase table found for {ticker!r} (expected {table!r})")

    prices = pd.read_sql(
        sa.text(
            f'''
            select
                trade_date as date,
                open as "Open",
                high as "High",
                low as "Low",
                close as "Close",
                value as "Value"
            from "{table}"
            where trade_date >= current_date - interval '{int(days)} days'
            order by trade_date
            '''
        ),
        db_engine,
        parse_dates=["date"],
        index_col="date",
    )
    for col in ("Open", "High", "Low", "Close", "Value"):
        prices[col] = pd.to_numeric(prices[col], errors="coerce")
    prices = prices.dropna(subset=["Open", "High", "Low", "Close"])
    prices = prices[~prices.index.duplicated(keep="last")].sort_index()
    if prices.empty:
        raise ValueError(f"Supabase table {table!r} returned no usable OHLC rows")

    # Value is peso turnover; estimate share volume via typical price.
    typical_price = (prices["High"] + prices["Low"] + prices["Close"]) / 3
    prices["Volume"] = prices["Value"] / typical_price.replace(0, float("nan"))
    prices["Volume"] = (
        pd.to_numeric(prices["Volume"], errors="coerce").fillna(0.0).clip(lower=0.0)
    )
    return clip_to_lookback(prices, days)


def get_hist_data(symbol: str) -> pd.DataFrame:
    ticker = symbol.strip().upper()
    csv_filename = f"./data/temp/{ticker}_data.csv"
    last_sync_date = get_last_sync_date(engine)
    df = load_cached(csv_filename, last_sync_date=last_sync_date)
    if df is None:
        df = load_price(engine, ticker)
        df.to_csv(csv_filename)
        logger.info(
            "Fetched and cached after sync %s: %s (%s rows, %sd through %s)",
            last_sync_date,
            csv_filename,
            len(df),
            LOOKBACK_DAYS,
            df.index.max().date(),
        )
    return df
