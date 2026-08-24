import matplotlib.pyplot as plt
import streamlit as st

from db.hist_data import get_hist_data
from model.fibonacci import plot_fibonacci_retracement
from ui.dashboard import render_footer


def _normalize_symbol(input_key: str) -> None:
    """Uppercase the form symbol before the script body runs."""
    raw = st.session_state.get(input_key, "")
    st.session_state[input_key] = str(raw).strip().upper()


def _render_fibonacci_chart(ticker: str, *, show_spinner: bool = False) -> bool:
    try:
        if show_spinner:
            with st.spinner(f"Loading {ticker} price data..."):
                df = get_hist_data(ticker)
                result = plot_fibonacci_retracement(ticker, df)
        else:
            df = get_hist_data(ticker)
            result = plot_fibonacci_retracement(ticker, df)
        st.pyplot(result.figure, width="stretch")
        plt.close(result.figure)
        return True
    except Exception as exc:
        st.error(f"Could not generate Fibonacci chart for {ticker}: {exc}")
        return False


def render_fibonacci_retracement() -> None:
    if "fibonacci_symbol" not in st.session_state:
        st.session_state.fibonacci_symbol = st.session_state.get("fibonacci_active_ticker") or ""

    st.write("")
    st.markdown(
        """
        <div class="section-title">📐 Fibonacci Retracement</div>
        <div class="section-sub">Find potential support and resistance levels</div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")
    st.markdown(
        """
        <style>
            input[placeholder="e.g. ALI"] { text-transform: uppercase; }
            div[data-testid="InputInstructions"] { visibility: hidden; }
            div[data-testid="stForm"] [data-testid="column"] {
                display: flex;
                align-items: center;
            }
            div[data-testid="stForm"] [data-testid="stTextInput"] {
                width: 100%;
            }
            div[data-testid="stForm"] [data-testid="stTextInput"] > div {
                margin-bottom: 0;
            }
            div[data-testid="stForm"] [data-testid="stTextInput"] input {
                height: 2.5rem;
                min-height: 2.5rem;
                box-sizing: border-box;
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
        st.markdown("**Symbol:**")

    with form_col:
        with st.form("fibonacci_form", clear_on_submit=False, border=False):
            input_col, button_col = st.columns([3, 1], vertical_alignment="center", gap="small")
            with input_col:
                st.text_input(
                    "symbol",
                    label_visibility="collapsed",
                    placeholder="e.g. ALI",
                    max_chars=10,
                    key="fibonacci_symbol",
                )
            with button_col:
                generate = st.form_submit_button(
                    "Generate",
                    type="secondary",
                    width="stretch",
                    on_click=_normalize_symbol,
                    args=("fibonacci_symbol",),
                )

    if generate:
        ticker = str(st.session_state.get("fibonacci_symbol", "")).strip().upper()
        if not ticker:
            st.warning("Enter a stock symbol.")
        elif _render_fibonacci_chart(ticker, show_spinner=True):
            st.session_state.fibonacci_active_ticker = ticker
    elif st.session_state.get("fibonacci_active_ticker"):
        _render_fibonacci_chart(st.session_state.fibonacci_active_ticker)

    st.write("")
    render_footer()
