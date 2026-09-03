import streamlit as st

from model.swingtrade import get_swing_trade_watchlist, get_swingtrade_dates
from ui.dashboard import render_footer

_ROW_HEIGHT = 35
_HEADER_HEIGHT = 38


def _table_height(row_count: int) -> int:
    return _HEADER_HEIGHT + max(row_count, 1) * _ROW_HEIGHT


def _render_watchlist_table(watchlist) -> None:
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
            "Support": st.column_config.TextColumn("Support"),
            "Resistance": st.column_config.TextColumn("Resistance"),
        },
    )


def render_swing_trade_watchlist() -> None:
    available_dates = get_swingtrade_dates()
    if "swingtrade_date" not in st.session_state:
        st.session_state.swingtrade_date = available_dates[0]
    if "swingtrade_active_date" not in st.session_state:
        st.session_state.swingtrade_active_date = st.session_state.swingtrade_date

    st.write("")
    st.markdown(
        """
        <div class="section-title">⭐ SWING TRADE WATCHLIST</div>
        <div class="section-sub">High probability setups for 3–10 day swing trades</div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")
    st.markdown(
        """
        <style>
            div[data-testid="InputInstructions"] { visibility: hidden; }
            div[data-testid="stForm"] [data-testid="column"] {
                display: flex;
                align-items: center;
            }
            div[data-testid="stForm"] [data-testid="stSelectbox"] {
                width: 100%;
            }
            div[data-testid="stForm"] [data-testid="stSelectbox"] > div {
                margin-bottom: 0;
            }
            div[data-testid="stForm"] [data-testid="stSelectbox"] [data-baseweb="select"] > div {
                min-height: 2.5rem;
            }
            div[data-testid="stForm"] [data-testid="stFormSubmitButton"],
            div[data-testid="stForm"] [data-testid="stButton"] {
                width: 100%;
            }
            div[data-testid="stForm"] [data-testid="stFormSubmitButton"] > button,
            div[data-testid="stForm"] [data-testid="stButton"] > button {
                height: 2.5rem;
                min-height: 2.5rem;
                margin: 0;
                box-sizing: border-box;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    label_col, form_col = st.columns([1, 4], vertical_alignment="center", width=450)

    with label_col:
        st.markdown("**Date:**")

    with form_col:
        with st.form("swingtrade_form", clear_on_submit=False, border=False):
            input_col, button_col = st.columns([3, 1], vertical_alignment="center", gap="small")
            with input_col:
                st.selectbox(
                    "date",
                    available_dates,
                    format_func=lambda value: value.strftime("%Y-%m-%d"),
                    label_visibility="collapsed",
                    key="swingtrade_date",
                )
            with button_col:
                generate = st.form_submit_button(
                    "Generate",
                    type="secondary",
                    width="stretch",
                )

    if generate:
        selected_date = st.session_state.swingtrade_date
        if selected_date not in available_dates:
            st.warning("Select a valid swing trade date.")
        else:
            with st.spinner("Scanning swing trade setups..."):
                watchlist = get_swing_trade_watchlist(selected_date)
            st.session_state.swingtrade_active_date = selected_date
            _render_watchlist_table(watchlist)
    elif st.session_state.get("swingtrade_active_date"):
        watchlist = get_swing_trade_watchlist(st.session_state.swingtrade_active_date)
        _render_watchlist_table(watchlist)

    st.write("")
    render_footer()
