import numpy as np
import pandas as pd
import streamlit as st

from .data import breadth


def get_nav_items() -> list[tuple[str, str]]:
    return [
        ("📊", "Market Overview"),
        ("⭐", "Swing Trade Watchlist"),
        ("📐", "Fibonacci Retracement"),
        # ("🏠", "Dashboard"),
        # ("📊", "Market Overview"),
        # ("🔎", "Stock Screener"),
        # ("⭐", "Watchlist"),
        # ("💡", "Swing Trade Ideas"),
        # ("🔔", "Alerts"),
        # ("📅", "Calendar"),
        # ("📰", "News"),
        # ("📘", "Learn"),
        # ("📝", "My Notes"),
    ]


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            """
            <div style="display:flex;align-items:center;gap:10px;padding:6px 0 20px 0;">
                <div style="font-size:26px;">🇵🇭</div>
                <div style="font-size:20px;font-weight:800;color:#fff;">Philippine Stock Exchange</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.radio(
            "nav",
            [f"{icon}  {label}" for icon, label in get_nav_items()],
            index=0,
            label_visibility="collapsed",
        )

        st.markdown("<hr style='border-color:#1c2333;margin:20px 0;'>", unsafe_allow_html=True)
        st.markdown("<div class='card-label'>Market Trend</div>", unsafe_allow_html=True)
        st.markdown("<div style='color:#26d07c;font-size:18px;font-weight:800;'>BULLISH</div>", unsafe_allow_html=True)

        trend_data = pd.DataFrame({"val": np.cumsum(np.random.randn(30)) + 20})
        st.line_chart(trend_data, height=100, width="stretch")

        st.markdown(
            f"""
            <div style="font-size:13px;margin-top:10px;">
                <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                    <span style="color:#8b93a7;">Advancers</span><span style="color:#26d07c;font-weight:700;">{breadth['advancers']}</span>
                </div>
                <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                    <span style="color:#8b93a7;">Decliners</span><span style="color:#f0555e;font-weight:700;">{breadth['decliners']}</span>
                </div>
                <div style="display:flex;justify-content:space-between;">
                    <span style="color:#8b93a7;">Unchanged</span><span style="color:#9aa2b8;font-weight:700;">{breadth['unchanged']}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
