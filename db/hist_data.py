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

DATABASE_URL = os.getenv("DB_URL")
if not DATABASE_URL:
    DATABASE_URL = st.secrets["DB_URL"]
    if not DATABASE_URL:
        raise ValueError("DB_URL not found in .env or streamlit secrets")


def normalize_database_url(url: str) -> str:
    """Ensure SQLAlchemy uses the installed psycopg v3 driver."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    if url.startswith("postgresql+psycopg2://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql+psycopg2://")
    return url


engine = sa.create_engine(normalize_database_url(DATABASE_URL))

os.makedirs("./data/temp", exist_ok=True)


def clip_to_lookback(prices: pd.DataFrame, days: int = LOOKBACK_DAYS) -> pd.DataFrame:
    cutoff = prices.index.max() - pd.Timedelta(days=days)
    return prices[prices.index >= cutoff].copy()


def price_table_name(ticker: str) -> str:
    return f"price_{ticker.strip().lower()}"


def get_db_latest_trade_date(
    db_engine: sa.Engine, ticker: str
) -> datetime.date | None:
    """Return max(trade_date) from Supabase for the ticker, or None if missing."""
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
            return None
        latest = conn.execute(
            sa.text(f'select max(trade_date) from "{table}"')
        ).scalar()
    if latest is None:
        return None
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


def load_cached(path: str, *, db_latest: datetime.date) -> pd.DataFrame | None:
    if not os.path.exists(path):
        return None
    if os.path.getsize(path) == 0:
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

    if last_date >= db_latest:
        cached = clip_to_lookback(cached)
        logger.info(
            "Using cached data through %s (db latest %s, %s rows, %sd): %s",
            last_date,
            db_latest,
            len(cached),
            LOOKBACK_DAYS,
            path,
        )
        return cached

    logger.info(
        "Cached data ends %s (db latest %s); clearing and downloading new data...",
        last_date,
        db_latest,
    )
    clear_cache(path)
    return None


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
        raise ValueError(f"No data found for {ticker!r} (expected {table!r})")

    prices = pd.read_sql(
        sa.text(
            f'''
            select
                trade_date as date,
                open as "Open",
                high as "High",
                low as "Low",
                close as "Close",
                volume as "Volume"
            from "{table}"
            where trade_date >= current_date - interval '{int(days)} days'
            order by trade_date
            '''
        ),
        db_engine,
        parse_dates=["date"],
        index_col="date",
    )
    for col in ("Open", "High", "Low", "Close", "Volume"):
        prices[col] = pd.to_numeric(prices[col], errors="coerce")
    prices = prices.dropna(subset=["Open", "High", "Low", "Close"])
    prices = prices[~prices.index.duplicated(keep="last")].sort_index()
    if prices.empty:
        raise ValueError(f"Data for {table!r} returned no usable OHLC rows")

    prices["Volume"] = prices["Volume"].fillna(0.0).clip(lower=0.0)
    return clip_to_lookback(prices, days)


def get_hist_data(symbol: str) -> pd.DataFrame:
    ticker = symbol.strip().upper()
    csv_filename = f"./data/temp/{ticker}_data.csv"
    db_latest = get_db_latest_trade_date(engine, ticker)
    if db_latest is None:
        raise ValueError(
            f"No data found for {ticker!r} "
            f"(expected {price_table_name(ticker)!r})"
        )

    df = load_cached(csv_filename, db_latest=db_latest)
    if df is None:
        df = load_price(engine, ticker)
        df.to_csv(csv_filename)
        logger.info(
            "Fetched and cached: %s (%s rows, %sd through %s, db latest %s)",
            csv_filename,
            len(df),
            LOOKBACK_DAYS,
            df.index.max().date(),
            db_latest,
        )
    return df
