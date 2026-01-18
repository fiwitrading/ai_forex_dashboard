import feedparser
import streamlit as st
import pandas as pd
from transformers import pipeline
import random

# === CONFIG STREAMLIT ===
st.set_page_config(page_title="AI Forex Macro Desk", layout="wide")
st.markdown("<h1 style='text-align:center;'>🤖 AI Forex Macro Desk</h1>", unsafe_allow_html=True)

# === 1. RSS FEEDS ȘTIRI ===
rss_feeds = {
    "Investing.com": "https://www.investing.com/rss/news_301.rss",
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

# === 2. NLP SENTIMENT ANALYSIS ===
sentiment_analyzer = pipeline("sentiment-analysis", model="cardiffnlp/twitter-roberta-base-sentiment")

impact_data = []
for item in news_items:
    sentiment = sentiment_analyzer(item["title"])[0]
    label = sentiment["label"]
    score = round(sentiment["score"], 2)

    # Corelare simplă cu perechile
    title_lower = item["title"].lower()
    if any(k in title_lower for k in ["fed", "usd", "america", "us dollar"]):
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
        "score": score,
        "source": item["source"],
        "link": item["link"]
    })

df = pd.DataFrame(impact_data)

# === 3. Rezumat AI per pereche ===
pairs = ["EUR/USD", "GBP/USD", "USD/JPY", "XAU/USD"]
cards = []
for p in pairs:
    pair_news = df[df['pair'] == p]
    if len(pair_news) > 0:
        avg_score = pair_news['score'].mean()
        # Simple logic pentru bullish/neutral/bearish
        if avg_score > 0.6:
            bias = "Bullish"
        elif avg_score < 0.4:
            bias = "Bearish"
        else:
            bias = "Neutral"
        # Rezumat AI simplu: primul titlu + sentiment
        summary = pair_news.iloc[0]['title']
    else:
        avg_score = 0.5
        bias = "Neutral"
        summary = "No major news"

    cards.append({
        "pair": p,
        "confidence": int(avg_score*100),
        "bias": bias,
        "summary": summary
    })

# === 4. UI CARDURI ===
st.subheader("Market bias analysis")
cols = st.columns(len(cards))
for i, card in enumerate(cards):
    with cols[i]:
        st.markdown(f"### {card['pair']}")
        st.markdown(f"**Bias:** {card['bias']}")
        st.progress(card['confidence'])
        st.info(card['summary'])
