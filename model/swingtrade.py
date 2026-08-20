import datetime
import logging
import os

import pandas as pd
import sqlalchemy as sa

from db.hist_data import engine

logger = logging.getLogger(__name__)

CACHE_DIR = "./data/temp"
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_PATH = os.path.join(CACHE_DIR, "swingtrade_latest.csv")

REQUIRED_COLUMNS = {"symbol", "date", "close", "support", "resistance"}
WATCHLIST_COLUMNS = [
    "Symbol",
    "Company Name",
    "Date",
    "Close",
    "Support",
    "Resistance",
]


def expected_latest_data_date(today: datetime.date | None = None) -> datetime.date:
    """Prices lag by 1 session; expect data through the prior trading day."""
    day = (today or datetime.date.today()) - datetime.timedelta(days=1)
    while day.weekday() >= 5:
        day -= datetime.timedelta(days=1)
    return day


def load_cached_swingtrade(path: str = CACHE_PATH) -> pd.DataFrame | None:
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
            "Using cached swingtrade through %s (%s rows): %s",
            last_date,
            len(cached),
            path,
        )
        return cached

    logger.info("Cached swingtrade ends %s; fetching latest from Supabase...", last_date)
    return None


def fetch_latest_swingtrade(db_engine: sa.Engine) -> pd.DataFrame:
    query = sa.text(
        """
        select *
        from swingtrade
        where date = (select max(date) from swingtrade)
        order by symbol
        """
    )
    df = pd.read_sql(query, db_engine, parse_dates=["date"])
    if df.empty:
        raise ValueError("Supabase table swingtrade returned no rows")
    return df


def get_swingtrade_dataframe() -> pd.DataFrame:
    """Return the latest swingtrade rows from cache or Supabase."""
    df = load_cached_swingtrade()
    if df is None:
        df = fetch_latest_swingtrade(engine)
        df.to_csv(CACHE_PATH, index=False)
        logger.info(
            "Fetched and cached: %s (%s rows through %s)",
            CACHE_PATH,
            len(df),
            df["date"].max().date(),
        )
    return df


def fetch_company_names(db_engine: sa.Engine, symbols: list[str]) -> dict[str, str]:
    names: dict[str, str] = {}
    with db_engine.connect() as conn:
        for symbol in symbols:
            table = f"price_{symbol.lower()}"
            name = conn.execute(
                sa.text(f'select company from "{table}" where company is not null limit 1')
            ).scalar()
            names[symbol] = name or ""
    return names


def format_peso(value: float) -> str:
    if pd.isna(value):
        return ""
    return f"₱{value:,.2f}"


def get_swing_trade_watchlist() -> pd.DataFrame:
    """Return swing trade watchlist formatted for the UI table."""
    df = get_swingtrade_dataframe()
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
                "Support": format_peso(row["support"]),
                "Resistance": format_peso(row["resistance"]),
            }
        )

    return pd.DataFrame(rows, columns=WATCHLIST_COLUMNS)
