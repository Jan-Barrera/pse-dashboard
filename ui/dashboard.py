from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import html
import numpy as np
import pandas as pd
import streamlit as st

from model.scrape_data import (
    SCRAPE_INTERVAL_SECONDS,
    get_indices,
    get_indices_updated_at,
    get_market_news,
    indices_needs_refresh,
    market_news_needs_refresh,
)

from .data import breadth, checklist_left, checklist_right, events, watchlist


def render_header() -> None:
    top_l, top_r = st.columns([3, 2])
    with top_l:
        st.markdown(
            """
            <div class="top-bar-title">PHILIPPINE STOCK MARKET</div>
            <div class="top-bar-sub">Your Edge for Smarter Swing Trades</div>
            """,
            unsafe_allow_html=True,
        )
    with top_r:
        now = datetime.now(ZoneInfo("Asia/Manila"))
        date_label = f"{now.strftime('%B')} {now.day}, {now.strftime('%Y')} &nbsp;•&nbsp; {now.strftime('%A')}"
        st.markdown(
            f"""
            <div style="display:flex;justify-content:flex-end;align-items:center;gap:18px;padding-top:8px;">
                <span style="color:#c7cce0;font-size:13px;">{date_label}</span>
                <span class="market-status">● Market Closed</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _draw_index_cards(indices: list[dict]) -> None:
    updated_at = get_indices_updated_at()
    if updated_at is not None:
        st.session_state["indices_updated_at"] = updated_at

    c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 1.1])
    cols_map = [c1, c2, c3, c4]
    for col, idx in zip(cols_map, indices):
        chart_series = pd.DataFrame({"v": np.cumsum(np.abs(np.random.randn(20))) + 5})
        change_class = "card-change-up" if idx["up"] else "card-change-down"
        change_arrow = "▲" if idx["up"] else "▼"
        with col:
            st.markdown(
                f"""
                <div class="card">
                    <div class="card-label">{idx['name']}</div>
                    <div class="card-value">{idx['value']}</div>
                    <div class="{change_class}">{change_arrow} {idx['change']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.line_chart(chart_series, height=70, width="stretch")
            if idx["value_b"]:
                st.markdown(
                    f"""
                    <div class="sub-stats">
                        <div><div class="sub-stat-label">Value</div><div class="sub-stat-value">{idx['value_b']}</div></div>
                        <div><div class="sub-stat-label">Volume</div><div class="sub-stat-value">{idx['vol']}</div></div>
                        <div><div class="sub-stat-label">Trades</div><div class="sub-stat-value">{idx['trades']}</div></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    with c5:
        st.markdown(
            f"""
            <div class="card" style="height: 100%;">
                <div class="card-label">Market Breadth</div>
                <div style="display:flex;align-items:center;gap:16px;margin-top:8px;">
                    <div style="font-size:40px;">🍩</div>
                    <div style="font-size:13px;">
                        <div style="margin-bottom:4px;"><span style="color:#26d07c;">●</span> {breadth['advancers']} Advancers ({breadth['advancers']*100//breadth['total']}%)</div>
                        <div style="margin-bottom:4px;"><span style="color:#f0555e;">●</span> {breadth['decliners']} Decliners ({breadth['decliners']*100//breadth['total']}%)</div>
                        <div><span style="color:#9aa2b8;">●</span> {breadth['unchanged']} Unchanged ({breadth['unchanged']*100//breadth['total']}%)</div>
                    </div>
                </div>
                <div style="color:#6b7386;font-size:12px;margin-top:10px;">Total Issues: {breadth['total']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


@st.fragment(run_every=timedelta(seconds=SCRAPE_INTERVAL_SECONDS))
def render_index_cards() -> None:
    if indices_needs_refresh():
        with st.spinner("Loading market indices from PSE..."):
            with st.skeleton(height=260):
                _draw_index_cards(get_indices())
    else:
        _draw_index_cards(get_indices())


def render_watchlist_header() -> None:
    h1, h2 = st.columns([2, 3])
    with h1:
        st.markdown(
            """
            <div class="section-title">🌟 SWING TRADE WATCHLIST</div>
            <div class="section-sub">High probability setups for 3–10 day swing trades</div>
            """,
            unsafe_allow_html=True,
        )
    with h2:
        f1, f2, f3, f4 = st.columns(4)
        f1.selectbox("Sector", ["All Sectors", "Holdings", "Financials", "Energy", "Property"], label_visibility="collapsed")
        f2.selectbox("Liquidity", ["Liquidity: Above Avg", "Liquidity: Below Avg"], label_visibility="collapsed")
        f3.selectbox("Volatility", ["Volatility: Moderate to High", "Volatility: Low"], label_visibility="collapsed")
        f4.button("⚙️ Customize", width="stretch")


def render_watchlist_table(df: pd.DataFrame) -> None:
    display_df = df.copy()
    display_df["#"] = display_df["#"].astype(str) + " ⭐"
    display_df["Trend"] = display_df["Trend"].map(
        lambda value: f"📈 {value}" if value == "Uptrend" else "〰️ Sideways"
    )
    st.dataframe(
        display_df,
        width="stretch",
        hide_index=True,
        column_config={
            "#": st.column_config.NumberColumn("#", format="%d"),
            "Ticker": st.column_config.TextColumn("Ticker"),
            "Company": st.column_config.TextColumn("Company"),
            "Sector": st.column_config.TextColumn("Sector"),
            "Last Price": st.column_config.TextColumn("Last Price"),
            "% Change": st.column_config.TextColumn("% Change"),
            "Volume": st.column_config.TextColumn("Volume"),
            "Avg Vol (20D)": st.column_config.TextColumn("Avg Vol (20D)"),
            "RSI (14)": st.column_config.NumberColumn("RSI (14)", format="%.1f"),
            "Trend": st.column_config.TextColumn("Trend"),
            "Support": st.column_config.TextColumn("Support"),
            "Resistance": st.column_config.TextColumn("Resistance"),
            "Swing Setup / Notes": st.column_config.TextColumn("Swing Setup / Notes"),
        },
    )


def _draw_market_news(news: list[tuple[str, str, str]]) -> None:
    news_html = """<div class='card'><div style="display:flex;justify-content:space-between;align-items:center;">
    <div class='section-title' style='font-size:15px;'>MARKET NEWS</div>
    <div class='section-sub' style='font-size:12px;'>
    <a href="https://www.pse.com.ph/press-room-archive/" target="_blank" rel="noopener noreferrer" style="text-decoration: none; color: inherit;">
        PSE Press Room
    </a>
    </div>
    </div><div style='margin-top:12px;'>"""
    if news:
        for date, headline, url in news:
            if url:
                headline_html = (
                    f'<a href="{html.escape(url, quote=True)}" target="_blank" '
                    f'rel="noopener noreferrer" style="color:#c7cce0;text-decoration:none;">'
                    f"{html.escape(headline)}</a>"
                )
            else:
                headline_html = html.escape(headline)
            news_html += (
                f"<div class='news-item' style='display: flex; gap: 15px;'>"
                f"<span class='news-date' style='min-width: 120px; flex-shrink: 0;'>{html.escape(date)}</span>"
                f"{headline_html}</div>"
            )
    else:
        news_html += "<div class='news-item' style='color:#8b93a7;'>No market news available.</div>"
    news_html += "</div></div>"
    st.markdown(news_html, unsafe_allow_html=True)


@st.fragment(run_every=timedelta(seconds=SCRAPE_INTERVAL_SECONDS))
def render_market_news() -> None:
    if market_news_needs_refresh():
        with st.spinner("Loading market news from PSE..."):
            with st.skeleton(height=220):
                _draw_market_news(get_market_news())
    else:
        _draw_market_news(get_market_news())


def render_bottom_panels() -> None:
    b1, b2 = st.columns(2)

    with b1:
        checklist_html = "<div class='card'><div class='section-title' style='font-size:15px;'>SWING TRADING CHECKLIST</div><div style='margin-top:12px;display:flex;gap:24px;'>"
        checklist_html += "<div>" + "".join([f"<div class='checklist-item'>✅ {item}</div>" for item in checklist_left]) + "</div>"
        checklist_html += "<div>" + "".join([f"<div class='checklist-item'>✅ {item}</div>" for item in checklist_right]) + "</div>"
        checklist_html += "</div></div>"
        st.markdown(checklist_html, unsafe_allow_html=True)

    with b2:
        render_market_news()


def render_footer() -> None:
    st.write("")
    updated_at = st.session_state.get("indices_updated_at") or get_indices_updated_at()
    if updated_at is None:
        data_label = "Data as of latest available market close"
    else:
        data_label = f"Data as of {updated_at.strftime('%B %d, %Y %I:%M %p PHT')} 🔄"
    st.markdown(
        f"""
        <div style="display:flex;justify-content:space-between;color:#4b5268;font-size:11px;border-top:1px solid #1e2540;padding-top:14px;">
            <span>DISCLAIMER: Information displayed is for reference only and does not constitute investment advice. Please do your own research and consult a licensed financial advisor.</span>
            <span>{data_label}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_dashboard() -> None:
    st.write("")
    render_header()
    st.write("")
    render_index_cards()
    st.write("")
    st.write("")
    render_watchlist_header()
    render_watchlist_table(watchlist)
    st.write("")
    st.write("")
    render_bottom_panels()
    render_footer()
