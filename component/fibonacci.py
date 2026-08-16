import matplotlib.pyplot as plt
import streamlit as st

from db.hist_data import get_hist_data
from model.fibonacci import plot_fibonacci_retracement
from ui.dashboard import render_footer


def _render_fibonacci_chart(ticker: str) -> None:
    try:
        with st.spinner(f"Loading {ticker} price data..."):
            df = get_hist_data(ticker)
            fig = plot_fibonacci_retracement(ticker, df)
        st.pyplot(fig, width="stretch")
        plt.close(fig)
    except Exception as exc:
        st.error(f"Could not generate Fibonacci chart for {ticker}: {exc}")


def render_fibonacci_retracement() -> None:
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
                symbol = st.text_input(
                    "symbol",
                    label_visibility="collapsed",
                    placeholder="e.g. ALI",
                    max_chars=10,
                    key="fibonacci_symbol",
                )
            with button_col:
                generate = st.form_submit_button("Generate", type="secondary", width="stretch")

    if generate:
        ticker = symbol.strip().upper()
        if not ticker:
            st.warning("Enter a stock symbol.")
        else:
            _render_fibonacci_chart(ticker)

    st.write("")
    render_footer()
