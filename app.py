import pandas as pd
import streamlit as st

from ui.dashboard import render_dashboard as _render_dashboard
from ui.data import watchlist
from ui.sidebar import render_sidebar
from ui.style import apply_global_styles


def render_table(df: pd.DataFrame) -> None:
    display_df = df.copy()
    display_df["#"] = display_df["#"].astype(str) + " ⭐"
    display_df["Trend"] = display_df["Trend"].map(
        lambda value: f"📈 {value}" if value == "Uptrend" else "〰️ Sideways"
    )
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )


st.set_page_config(
    page_title="Philippine Stock Market Dashboard",
    page_icon="🇵🇭",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_global_styles()
render_sidebar()
_render_dashboard()
