import streamlit as st

from model.prebreakout import get_prebreakout_watchlist
from ui.dashboard import render_footer

_ROW_HEIGHT = 35
_HEADER_HEIGHT = 38


def _table_height(row_count: int) -> int:
    return _HEADER_HEIGHT + max(row_count, 1) * _ROW_HEIGHT


@st.cache_data(ttl=900, show_spinner=False)
def _load_watchlist():
    return get_prebreakout_watchlist()


def render_prebreakout_watchlist() -> None:
    st.write("")
    st.markdown(
        """
        <div class="section-title">🔭 PRE-BREAKOUT WATCHLIST</div>
        <div class="section-sub">Stocks compressing near resistance ahead of a potential breakout</div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")
    with st.spinner("Scanning pre-breakout setups..."):
        watchlist = _load_watchlist()
    st.markdown(
        """
        <style>
            [data-testid="stDataFrame"] > div {
                overflow: hidden !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.dataframe(
        watchlist,
        width="stretch",
        height=_table_height(len(watchlist)),
        row_height=_ROW_HEIGHT,
        hide_index=True,
        column_config={
            "Symbol": st.column_config.TextColumn("Symbol"),
            "Company Name": st.column_config.TextColumn("Company Name"),
            "Date": st.column_config.TextColumn("Date"),
            "Close": st.column_config.TextColumn("Close"),
            "Status": st.column_config.TextColumn("Status"),
            "Source": st.column_config.TextColumn("Source"),
            "Note": st.column_config.TextColumn("Note"),
        },
    )
    render_footer()
