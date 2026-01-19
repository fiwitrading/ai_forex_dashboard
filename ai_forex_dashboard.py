import feedparser
import streamlit as st
import pandas as pd
import datetime
import random
from transformers import pipeline

# === SETUP PAGE ===
st.set_page_config(page_title="AI Macro Desk", layout="wide", page_icon="🤖")
st.markdown(
    "<h1 style='text-align:center; color:#74E291;'>🤖 AI Macro Desk</h1>"
    "<h3 style='text-align:center; color:gray;'>Live market bias & economic impact dashboard</h3>",
    unsafe_allow_html=True
)

# === 1. FEEDURI DE ȘTIRI ===
rss_feeds = {
    "Investing.com": "https://www.investing.com/rss/news_301.rss",
    "Bloomberg Economics": "https://feeds.bloomberg.com/economics/news.rss",
    "Forex Factory": "https://www.forexfactory.com/ffcal_week_this.xml"
}

news_items = []
for name, url in rss_feeds.items():
    feed = feedparser.parse(url)
    for entry in feed.entries[:5]:
        news_items.append({
            "source": name,
            "title": entry.title,
            "link": entry.link
        })

# === 2. AI SENTIMENT ===
sentiment_analyzer = pipeline("sentiment-analysis", model="cardiffnlp/twitter-roberta-base-sentiment")

impact_data = []
for item in news_items:
    sentiment = sentiment_analyzer(item["title"])[0]
    label = sentiment["label"]
    score = sentiment["score"]

    title_lower = item["title"].lower()
    if any(k in title_lower for k in ["usd", "fed", "america", "us dollar"]):
        pair = "EUR/USD"
    elif any(k in title_lower for k in ["uk", "pound", "boe", "british"]):
        pair = "GBP/USD"
    elif any(k in title_lower for k in ["japan", "yen", "boj"]):
        pair = "USD/JPY"
    elif any(k in title_lower for k in ["gold", "xau"]):
        pair = "XAU/USD"
    else:
        pair = "Other"

    impact_data.append({
        "pair": pair,
        "title": item["title"],
        "sentiment": label,
        "score": round(score, 2),
        "source": item["source"],
        "link": item["link"]
    })

df = pd.DataFrame(impact_data)

# === 3. GENERARE BIAS + CONFIDENCE ===
pairs = ["EUR/USD", "GBP/USD", "USD/JPY", "XAU/USD"]
cards = []
for p in pairs:
    pair_news = df[df["pair"] == p]
    if len(pair_news) > 0:
        avg_score = pair_news["score"].mean()
        if avg_score > 0.6:
            bias = "Bullish"
            color = "#16C47F"
        elif avg_score < 0.4:
            bias = "Bearish"
            color = "#D44D5C"
        else:
            bias = "Neutral"
            color = "#D4D4D4"
        summary = pair_news.iloc[0]["title"]
    else:
        avg_score = 0.5
        bias = "Neutral"
        color = "#D4D4D4"
        summary = "No major news currently affecting this pair."

    cards.append({
        "pair": p,
        "confidence": int(avg_score * 100),
        "bias": bias,
        "color": color,
        "summary": summary
    })

# === 4. AFIȘARE CARDURI ===
st.subheader("📈 Market Bias Analysis (auto-updates every 10 min)")
cols = st.columns(4)
for i, card in enumerate(cards):
    with cols[i]:
        st.markdown(
            f"""
            <div style="background-color:#0C0F11; padding:15px; border-radius:12px; border:1px solid #1E242A;">
                <h3 style="color:white; text-align:center;">{card['pair']}</h3>
                <h4 style="color:{card['color']}; text-align:center;">{card['bias']}</h4>
                <div style="background:#1E242A; border-radius:10px;">
                    <div style="width:{card['confidence']}%; background:{card['color']}; height:10px; border-radius:10px;"></div>
                </div>
                <p style="color:gray; margin-top:8px; font-size:14px;">Confidence: {card['confidence']}%</p>
                <p style="color:#A9B2BA; font-size:13px;">💡 AI Analysis: {card['summary']}</p>
            </div>
            """,
            unsafe_allow_html=True
        )

# === 5. ECONOMIC EVENTS (IMPACT MEDIU ȘI MARE) ===
st.markdown("---")
st.subheader("🗓️ Upcoming High & Medium Impact Events")

# Parse ForexFactory feed pentru evenimente economice
factory_feed = feedparser.parse("https://www.forexfactory.com/ffcal_week_this.xml")
events = []
for entry in factory_feed.entries[:20]:
    title = entry.title
    if any(x in title.lower() for x in ["high impact", "medium impact"]):
        events.append({
            "event": title.replace("High Impact Expected", "🔥 High Impact").replace("Medium Impact Expected", "⚠️ Medium Impact"),
            "time": entry.published if "published" in entry else "N/A"
        })

if len(events) > 0:
    events_df = pd.DataFrame(events)
    st.table(events_df)
else:
    st.info("No upcoming medium/high impact events found.")

# === 6. AUTO REFRESH ===
st.markdown("<p style='text-align:center; color:gray; font-size:13px;'>Last update: " + 
            datetime.datetime.now().strftime("%H:%M:%S") + 
            " | Auto-refresh every 10 minutes</p>", unsafe_allow_html=True)
st.experimental_rerun()
