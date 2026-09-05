import datetime
import logging

import pandas as pd
import sqlalchemy as sa

from db.hist_data import engine

logger = logging.getLogger(__name__)

WATCHLIST_COLUMNS = [
    "Symbol",
    "Company Name",
    "Date",
    "Close",
    "Support",
    "Resistance",
]


def fetch_swingtrade_dates(
    db_engine: sa.Engine, limit: int = 10
) -> list[datetime.date]:
    """Return the latest `limit` distinct swingtrade dates, newest first."""
    query = sa.text(
        """
        select distinct date
        from swingtrade
        order by date desc
        limit :limit
        """
    )
    with db_engine.connect() as conn:
        rows = conn.execute(query, {"limit": limit}).scalars().all()
    dates: list[datetime.date] = []
    for row in rows:
        if isinstance(row, datetime.datetime):
            dates.append(row.date())
        else:
            dates.append(row)
    if not dates:
        raise ValueError("Supabase table swingtrade returned no dates")
    return dates


def get_swingtrade_dates(limit: int = 10) -> list[datetime.date]:
    """Return the latest swingtrade dates available in Supabase."""
    return fetch_swingtrade_dates(engine, limit=limit)


def fetch_latest_swingtrade(db_engine: sa.Engine) -> pd.DataFrame:
    latest_date = fetch_swingtrade_dates(db_engine, limit=1)[0]
    return fetch_swingtrade_for_date(db_engine, latest_date)


def fetch_swingtrade_for_date(
    db_engine: sa.Engine, trade_date: datetime.date
) -> pd.DataFrame:
    query = sa.text(
        """
        select *
        from swingtrade
        where date = :trade_date
        order by symbol
        """
    )
    df = pd.read_sql(
        query,
        db_engine,
        params={"trade_date": trade_date},
        parse_dates=["date"],
    )
    if df.empty:
        raise ValueError(
            f"Supabase table swingtrade returned no rows for {trade_date}"
        )
    return df


def get_swingtrade_dataframe(
    trade_date: datetime.date | None = None,
) -> pd.DataFrame:
    """Return swingtrade rows for `trade_date`, or the latest date when omitted."""
    if trade_date is None:
        return fetch_latest_swingtrade(engine)
    return fetch_swingtrade_for_date(engine, trade_date)


def fetch_company_names(db_engine: sa.Engine, symbols: list[str]) -> dict[str, str]:
    names: dict[str, str] = {}
    with db_engine.connect() as conn:
        for symbol in symbols:
            table = f"price_{symbol.lower()}"
            name = conn.execute(
                sa.text(f'select name from "{table}" where name is not null limit 1')
            ).scalar()
            names[symbol] = name or ""
    return names


def format_peso(value: float) -> str:
    if pd.isna(value):
        return ""
    return f"₱{value:,.2f}"


def get_swing_trade_watchlist(
    trade_date: datetime.date | None = None,
) -> pd.DataFrame:
    """Return swing trade watchlist formatted for the UI table."""
    df = get_swingtrade_dataframe(trade_date)
    if df.empty:
        return pd.DataFrame(columns=WATCHLIST_COLUMNS)

    companies = fetch_company_names(engine, df["symbol"].tolist())
    rows = []
    for _, row in df.iterrows():
        symbol = row["symbol"]
        row_date = row["date"]
        date_label = (
            pd.Timestamp(row_date).strftime("%Y-%m-%d")
            if pd.notna(row_date)
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
