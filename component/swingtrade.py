import pandas as pd
import streamlit as st

from ui.dashboard import render_footer


def render_swing_trade_watchlist() -> None:
    st.write("")
    st.markdown(
        """
        <div class="section-title">⭐ SWING TRADE WATCHLIST</div>
        <div class="section-sub">Track symbols and closing prices for swing trade setups</div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")
    empty_watchlist = pd.DataFrame(columns=["Symbol", "Company Name", "Date", "Close"])
    st.dataframe(
        empty_watchlist,
        width="stretch",
        hide_index=True,
        column_config={
            "Symbol": st.column_config.TextColumn("Symbol"),
            "Company Name": st.column_config.TextColumn("Company Name"),
            "Date": st.column_config.TextColumn("Date"),
            "Close": st.column_config.TextColumn("Close"),
        },
    )
    render_footer()
