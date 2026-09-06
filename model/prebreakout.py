import datetime
import logging

import pandas as pd
import sqlalchemy as sa

from db.hist_data import engine
from model.swingtrade import fetch_company_names, format_peso

logger = logging.getLogger(__name__)

WATCHLIST_COLUMNS = [
    "Symbol",
    "Company Name",
    "Date",
    "Close",
    "Status",
    "Source",
    "Note",
]


def fetch_prebreakout_dates(
    db_engine: sa.Engine, limit: int = 10
) -> list[datetime.date]:
    """Return the latest `limit` distinct prebreakout dates, newest first."""
    query = sa.text(
        """
        select distinct date
        from prebreakout_results
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
        raise ValueError("Supabase table prebreakout_results returned no dates")
    return dates


def get_prebreakout_dates(limit: int = 10) -> list[datetime.date]:
    """Return the latest prebreakout dates available in Supabase."""
    return fetch_prebreakout_dates(engine, limit=limit)


def fetch_latest_prebreakout(db_engine: sa.Engine) -> pd.DataFrame:
    latest_date = fetch_prebreakout_dates(db_engine, limit=1)[0]
    return fetch_prebreakout_for_date(db_engine, latest_date)


def fetch_prebreakout_for_date(
    db_engine: sa.Engine, trade_date: datetime.date
) -> pd.DataFrame:
    query = sa.text(
        """
        select symbol, date, status, close, source, note
        from prebreakout_results
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
            f"Supabase table prebreakout_results returned no rows for {trade_date}"
        )
    return df


def get_prebreakout_dataframe(
    trade_date: datetime.date | None = None,
) -> pd.DataFrame:
    """Return prebreakout rows for `trade_date`, or the latest date when omitted."""
    if trade_date is None:
        return fetch_latest_prebreakout(engine)
    return fetch_prebreakout_for_date(engine, trade_date)


def get_prebreakout_watchlist(
    trade_date: datetime.date | None = None,
) -> pd.DataFrame:
    """Return pre-breakout watchlist formatted for the UI table."""
    df = get_prebreakout_dataframe(trade_date)
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
                "Status": row.get("status") or "",
                "Source": row.get("source") or "",
                "Note": row.get("note") or "",
            }
        )

    return pd.DataFrame(rows, columns=WATCHLIST_COLUMNS)
