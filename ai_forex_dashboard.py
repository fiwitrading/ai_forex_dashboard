import feedparser
import streamlit as st
import pandas as pd
import datetime
from transformers import pipeline
from streamlit_autorefresh import st_autorefresh

# === CONFIG PAGE ===
st.set_page_config(page_title="AI Macro Desk", layout="wide", page_icon="🤖")

st.markdown(
    "<h1 style='text-align:center; color:#74E291;'>🤖 AI Macro Desk</h1>"
    "<h3 style='text-align:center; color:gray;'>Live Market Bias & Economic Impact Dashboard</h3>",
    unsafe_allow_html=True
)

# === AUTO REFRESH (10 minute) ===
st_autorefresh(interval=600000, key="datarefresh")

# === 1. RSS ȘTIRI ECONOMICE ===
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

# === 2. AI SENTIMENT ANALYSIS ===
st.subheader("📊 Market Bias Analysis (auto-updates every 10 min)")
sentiment_analyzer = pipeline("sentiment-analysis", model="cardiffnlp/twitter-roberta-base-sentiment")

impact_data = []
for item in news_items:
    sentiment = sentiment_analyzer(item["title"])[0]
    label = sentiment["label"]
    score = sentiment["score"]

    title_lower = item["title"].lower()
    if any(k in title_lower for k in ["usd", "fed", "america", "us dollar"]):
        pair = "EUR/USD"
    elif any(k in title_lower for k in ["uk", "pound"]):
