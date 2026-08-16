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


def expected_latest_data_date(today: datetime.date | None = None) -> datetime.date:
    """Supabase prices lag by 1 session; expect data through the prior trading day."""
    day = (today or datetime.date.today()) - datetime.timedelta(days=1)
    while day.weekday() >= 5:  # Sat/Sun -> previous Friday
        day -= datetime.timedelta(days=1)
    return day


def clip_to_lookback(prices: pd.DataFrame, days: int = LOOKBACK_DAYS) -> pd.DataFrame:
    cutoff = prices.index.max() - pd.Timedelta(days=days)
    return prices[prices.index >= cutoff].copy()


def load_cached(path: str) -> pd.DataFrame | None:
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return None
    try:
        cached = pd.read_csv(path, parse_dates=["date"], index_col="date")
    except (pd.errors.EmptyDataError, ValueError, KeyError):
        return None
    required = {"Open", "High", "Low", "Close", "Volume"}
    if cached.empty or not required.issubset(cached.columns):
        return None
    cached = cached[~cached.index.duplicated(keep="last")].sort_index()
    last_date = cached.index.max().date()
    expected = expected_latest_data_date()
    if last_date >= expected:
        cached = clip_to_lookback(cached)
        logger.info(
            "Using cached data through %s (%s rows, %sd): %s",
            last_date,
            len(cached),
            LOOKBACK_DAYS,
            path,
        )
        return cached
    logger.info(
        "Cached data ends %s (expected >= %s); fetching newer data from Supabase...",
        last_date,
        expected,
    )
    return None


def load_price(db_engine: sa.Engine, ticker: str, days: int = LOOKBACK_DAYS) -> pd.DataFrame:
    """Load last `days` of OHLC from Supabase `price_{symbol}`."""
    table = f"price_{ticker.lower()}"
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
    csv_filename = f"./data/temp/{symbol}_data.csv"
    df = load_cached(csv_filename)
    if df is None:
        df = load_price(engine, symbol)
        df.to_csv(csv_filename)
        logger.info(
            "Fetched and cached: %s (%s rows, %sd through %s)",
            csv_filename,
            len(df),
            LOOKBACK_DAYS,
            df.index.max().date(),
        )
    return df