import streamlit as st
import feedparser
import pandas as pd
from transformers import pipeline
import numpy as np

st.set_page_config(page_title="AI Insights", layout="wide")
st.title("🤖 AI Market Insights")
st.caption("Aggregated macro sentiment from multiple news sources")

# === 1️⃣ RSS MULTIPLE SOURCES ===
rss_feeds = {
    "ForexFactory": "https://www.forexfactory.com/ffcal_week_this.xml",
    "Investing.com": "https://www.investing.com/rss/news_301.rss",
    "Bloomberg": "https://feeds.bloomberg.com/economics/news.rss",
    "DailyFX": "https://www.dailyfx.com/feeds/all"
}

st.info("Fetching latest news from multiple sources...")

news_items = []
for name, url in rss_feeds.items():
    feed = feedparser.parse(url)
    for entry in feed.entries[:10]:
        news_items.append({
            "source": name,
            "title": entry.title
        })

df = pd.DataFrame(news_items)
st.write(f"Total news items collected: {len(df)}")

# === 2️⃣ AI SENTIMENT ANALYSIS ===
sentiment_analyzer = pipeline("sentiment-analysis", model="cardiffnlp/twitter-roberta-base-sentiment")

results = []
for _, row in df.iterrows():
    title = row["title"]
    sentiment = sentiment_analyzer(title)[0]
    label = sentiment["label"]
    score = sentiment["score"]

    # simple symbol mapping
    title_lower = title.lower()
    if any(k in title_lower for k in ["usd", "dollar", "fed", "america"]):
        symbol = "USD"
    elif any(k in title_lower for k in ["eur", "euro", "ecb"]):
        symbol = "EUR"
    elif any(k in title_lower for k in ["gbp", "pound", "boe", "uk"]):
        symbol = "GBP"
    elif any(k in title_lower for k in ["jpy", "yen", "boj"]):
        symbol = "JPY"
    elif any(k in title_lower for k in ["gold", "xau"]):
        symbol = "XAU"
    else:
        symbol = "OTHER"

    results.append({
        "Symbol": symbol,
        "Sentiment": label,
        "Score": score,
        "Title": title,
        "Source": row["source"]
    })

sent_df = pd.DataFrame(results)

# === 3️⃣ AGGREGATED SENTIMENT PER SYMBOL ===
symbols = ["USD", "EUR", "GBP", "JPY", "XAU"]
insights = []

for sym in symbols:
    sub = sent_df[sent_df["Symbol"] == sym]
    if len(sub) == 0:
        avg = 0.5
        label = "Neutral"
    else:
        avg = np.mean(sub["Score"])
        pos_count = len(sub[sub["Sentiment"] == "POSITIVE"])
        neg_count = len(sub[sub["Sentiment"] == "NEGATIVE"])
        if pos_count > neg_count:
            label = "Bullish"
        elif neg_count > pos_count:
            label = "Bearish"
        else:
            label = "Neutral"
    insights.append({
        "Symbol": sym,
        "Bias": label,
        "Confidence": int(avg * 100),
        "News Count": len(sub)
    })

insights_df = pd.DataFrame(insights)

# === 4️⃣ VISUAL DISPLAY ===
cols = st.columns(len(symbols))
for i, row in enumerate(insights_df.itertuples()):
    if row.Bias == "Bullish":
        color = "#16C47F"
    elif row.Bias == "Bearish":
        color = "#D44D5C"
    else:
        color = "#D4D4D4"

    with cols[i]:
        st.markdown(
            f"""
            <div style="background-color:#0C0F11; padding:15px; border-radius:12px; border:1px solid #1E242A;">
                <h3 style="color:white; text-align:center;">{row.Symbol}</h3>
                <h4 style="color:{color}; text-align:center;">{row.Bias}</h4>
                <div style="background:#1E242A; border-radius:10px;">
                    <div style="width:{row.Confidence}%; background:{color}; height:10px; border-radius:10px;"></div>
                </div>
                <p style="color:gray; text-align:center; font-size:13px;">Confidence: {row.Confidence}%<br>Articles: {row._4}</p>
            </div>
            """,
            unsafe_allow_html=True
        )

# === 5️⃣ SUMMARY TEXT ===
bullish = [r.Symbol for r in insights_df.itertuples() if r.Bias == "Bullish"]
bearish = [r.Symbol for r in insights_df.itertuples() if r.Bias == "Bearish"]
neutral = [r.Symbol for r in insights_df.itertuples() if r.Bias == "Neutral"]

summary_text = f"""
🧠 **AI Market Summary**

**Bullish bias:** {', '.join(bullish) if bullish else '—'}  
**Bearish bias:** {', '.join(bearish) if bearish else '—'}  
**Neutral:** {', '.join(neutral) if neutral else '—'}  

Based on aggregated sentiment from {len(df)} news articles across major sources (ForexFactory, Investing, Bloomberg, DailyFX).
"""

st.markdown(summary_text)

