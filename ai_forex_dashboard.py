#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import feedparser
import streamlit as st
import pandas as pd
import datetime
import time
import re
from math import exp
from typing import List, Dict
from transformers import pipeline
from streamlit_autorefresh import st_autorefresh

# === CONFIG PAGE ===
st.set_page_config(page_title="AI Macro Desk", layout="wide", page_icon="🤖")

st.markdown(
    "<h1 style='text-align:center; color:#74E291;'>🤖 AI Macro Desk</h1>"
    "<h3 style='text-align:center; color:gray;'>Live Market Bias & Economic Impact Dashboard</h3>",
    unsafe_allow_html=True
)

# Auto refresh (10 minutes)
st_autorefresh(interval=600000, key="datarefresh")

# === USER TUNABLE SETTINGS ===
with st.expander("Settings (feeds, items per feed, source weights)", True):
    items_per_feed = st.number_input("Items per feed (max per source)", min_value=3, max_value=50, value=8, step=1)
    recency_half_life_hours = st.number_input("Recency half-life (hours) — how fast old articles lose weight", min_value=1, max_value=168, value=72)
    # Source priority weights (can be extended)
    source_weights = {
        "Reuters": 1.2,
        "Bloomberg Economics": 1.3,
        "Investing.com": 1.0,
        "CNBC": 1.0,
        "MarketWatch": 1.0,
        "Forex Factory": 0.9,
        "Default": 1.0
    }

# === RSS FEEDS ===
# You can add/remove feeds here
rss_feeds = {
    "Investing.com": "https://www.investing.com/rss/news_301.rss",
    "Bloomberg Economics": "https://feeds.bloomberg.com/economics/news.rss",
    "Forex Factory": "https://www.forexfactory.com/ffcal_week_this.xml",
    "Reuters": "http://feeds.reuters.com/reuters/businessNews",
    "CNBC": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "MarketWatch": "https://feeds.marketwatch.com/marketwatch/topstories/"
}

# === KEYWORDS / LABELS PER PAIR ===
PAIR_KEYWORDS = {
    "EUR/USD": ["eurusd", "euro", "ecb", "europe", "eurozone", "european central bank", "eurostat", "bundesbank", "eur"],
    "GBP/USD": ["gbpusd", "pound", "sterling", "bank of england", "boe", "uk", "united kingdom", "britain", "gbp"],
    "USD/JPY": ["usdjpy", "yen", "boj", "bank of japan", "tokyo", "japan", "jpy"],
    "XAU/USD": ["gold", "xau", "spot gold", "precious metal", "gold price", "xauusd"],
}

PAIR_LABELS = list(PAIR_KEYWORDS.keys())

# === UTIL: text cleaning ===
def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"http\S+", "", text)  # remove URLs
    text = re.sub(r"\s+", " ", text).strip()
    return text

# === CACHING: pipelines so models are loaded once ===
@st.cache_resource(ttl=3600)
def get_sentiment_pipeline():
    try:
        return pipeline("sentiment-analysis", model="cardiffnlp/twitter-roberta-base-sentiment")
    except Exception:
        # Fallback to a more generic model if unavailable
        return pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")

@st.cache_resource(ttl=3600)
def get_zero_shot_pipeline():
    try:
        return pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
    except Exception:
        return None

@st.cache_resource(ttl=3600)
def get_summarizer_pipeline():
    try:
        return pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")
    except Exception:
        return None

sentiment_pipeline = get_sentiment_pipeline()
zero_shot = get_zero_shot_pipeline()
summarizer = get_summarizer_pipeline()

# === 1. FETCH AND COLLECT NEWS ===
st.subheader("📊 Market Bias Analysis (auto-updates every 10 min)")

news_items = []
now = datetime.datetime.utcnow()

for name, url in rss_feeds.items():
    try:
        feed = feedparser.parse(url)
        entries = feed.entries[:items_per_feed]
        for entry in entries:
            title = clean_text(getattr(entry, "title", "") or "")
            summary = clean_text(getattr(entry, "summary", "") or getattr(entry, "description", "") or "")
            link = getattr(entry, "link", "")
            published = None
            # try multiple published fields
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published = datetime.datetime.fromtimestamp(time.mktime(entry.published_parsed))
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                published = datetime.datetime.fromtimestamp(time.mktime(entry.updated_parsed))
            elif hasattr(entry, "published"):
                try:
                    published = pd.to_datetime(entry.published).to_pydatetime()
                except Exception:
                    published = None

            # fallback: items without title are ignored
            if not title:
                continue

            news_items.append({
                "source": name,
                "title": title,
                "summary": summary,
                "link": link,
                "published": published
            })
    except Exception as e:
        st.warning(f"Feed {name} failed: {e}")

if len(news_items) == 0:
    st.info("No news fetched from feeds. Check feed URLs or network.")
    st.stop()

# === 2. DETERMINE RELEVANT PAIR FOR EACH ITEM ===
def match_pair_by_keywords(text: str) -> str:
    t = text.lower()
    for pair, kws in PAIR_KEYWORDS.items():
        for kw in kws:
            if kw in t:
                return pair
    return None

# Precompute combined text for classification
for n in news_items:
    combined = f"{n['title']} . {n['summary']}"
    n["text"] = combined

# First pass: keyword matching
for n in news_items:
    pair = match_pair_by_keywords(n["text"])
    n["pair"] = pair if pair else "Other"

# For items not matched by keywords, use zero-shot classification if available
unmatched = [n for n in news_items if n["pair"] == "Other"]
if zero_shot and len(unmatched) > 0:
    try:
        texts = [u["text"] for u in unmatched]
        # zero-shot supports batch
        z_results = zero_shot(texts, PAIR_LABELS, multi_label=False)
        # z_results can be a dict for single input or list for many
        if isinstance(z_results, dict):
            z_results = [z_results]
        for u, res in zip(unmatched, z_results):
            # assign top label only if score reasonably high (>=0.3)
            label = res["labels"][0]
            score = res["scores"][0]
            if score >= 0.3:
                u["pair"] = label
    except Exception:
        pass

# === 3. SENTIMENT ANALYSIS (batch) ===
# Use pipeline in batch mode to be faster
texts = [n["title"] for n in news_items]
sent_results = []
try:
    sent_results = sentiment_pipeline(texts, truncation=True)
except Exception:
    # fallback to single evaluation if batching fails
    sent_results = [sentiment_pipeline(t) for t in texts]

# Map sentiment labels to numeric polarity
def sentiment_to_numeric(label: str) -> float:
    lab = label.lower()
    if "positive" in lab or "pos" in lab:
        return 1.0
    if "negative" in lab or "neg" in lab:
        return 0.0
    # neutral or others
    return 0.5

# Attach sentiment to news_items
for n, s in zip(news_items, sent_results):
    # s may be dict or list depending on pipeline call
    if isinstance(s, list):
        s = s[0]
    label = s.get("label", "")
    score = float(s.get("score", 0.0))
    n["sent_label"] = label
    n["sent_score"] = score
    n["sent_value"] = sentiment_to_numeric(label)

# === 4. WEIGHTING: recency and source weight ===
def recency_weight(published: datetime.datetime, half_life_hours: float) -> float:
    if published is None:
        return 0.2  # low weight for unknown time
    age_hours = max((now - published).total_seconds() / 3600.0, 0.0)
    # exponential decay: weight = 0.5 at half_life_hours
    lam = - (1.0 / half_life_hours) * (0.693147)  # ln(0.5) approx -0.693147
    weight = exp(lam * age_hours)
    return weight

for n in news_items:
    src_w = source_weights.get(n["source"], source_weights.get("Default", 1.0))
    r_w = recency_weight(n.get("published"), recency_half_life_hours)
    n["weight"] = src_w * r_w

# === 5. AGGREGARE PER PERECHE ===
pairs = PAIR_LABELS.copy()  # only known pairs
agg = {}
for p in pairs:
    items = [n for n in news_items if n["pair"] == p]
    if not items:
        agg[p] = {
            "count": 0,
            "weighted_score": 0.5,
            "bias": "Neutral",
            "color": "#D4D4D4",
            "top_titles": [],
            "pos": 0, "neu": 0, "neg": 0,
            "explanation": "No recent news matched this pair."
        }
        continue

    # weighted average of sent_value
    weighted_sum = sum(n["sent_value"] * n["weight"] for n in items)
    total_w = sum(n["weight"] for n in items) or 1.0
    weighted_score = weighted_sum / total_w

    # counts
    pos = sum(1 for n in items if n["sent_value"] > 0.75)
    neu = sum(1 for n in items if 0.4 <= n["sent_value"] <= 0.75)
    neg = sum(1 for n in items if n["sent_value"] < 0.4)

    # bias thresholds (customizable)
    if weighted_score >= 0.62:
        bias = "Bullish"
        color = "#16C47F"
    elif weighted_score <= 0.38:
        bias = "Bearish"
        color = "#D44D5C"
    else:
        bias = "Neutral"
        color = "#D4D4D4"

    # top titles by weight
    sorted_items = sorted(items, key=lambda x: x["weight"] * x["sent_score"], reverse=True)
    top_titles = [{
        "title": s["title"],
        "link": s["link"],
        "source": s["source"],
        "published": s["published"].strftime("%Y-%m-%d %H:%M") if s.get("published") else "N/A",
        "sent_label": s["sent_label"],
        "sent_score": round(s["sent_score"], 3),
        "weight": round(s["weight"], 3)
    } for s in sorted_items[:5]]

    # short explanation: try to summarize top titles or build explanation heuristically
    explanation = ""
    if summarizer and len(sorted_items) > 0:
        try:
            # feed concatenated top titles to summarizer
            concat = " ".join(t["title"] for t in sorted_items[:6])
            # summarizer expects longer text; guard length
            summary = summarizer(concat, max_length=50, min_length=15, do_sample=False)[0]["summary_text"]
            explanation = summary
        except Exception:
            explanation = sorted_items[0]["title"]
    else:
        # heuristic explanation from top items
        explanation = sorted_items[0]["title"]

    agg[p] = {
        "count": len(items),
        "weighted_score": round(weighted_score, 3),
        "bias": bias,
        "color": color,
        "top_titles": top_titles,
        "pos": pos, "neu": neu, "neg": neg,
        "explanation": explanation
    }

# === 6. UI: Cards with richer info ===
cols = st.columns(len(pairs))
for i, p in enumerate(pairs):
    card = agg[p]
    with cols[i]:
        st.markdown(
            f"""
            <div style="background-color:#0C0F11; padding:15px; border-radius:12px; border:1px solid #1E242A; min-height:200px;">
                <h3 style="color:white; text-align:center;">{p}</h3>
                <h4 style="color:{card['color']}; text-align:center;">{card['bias']} ({int(card['weighted_score']*100)}%)</h4>
                <div style="background:#1E242A; border-radius:10px; height:12px;">
                    <div style="width:{int(card['weighted_score']*100)}%; background:{card['color']}; height:12px; border-radius:10px;"></div>
                </div>
                <p style="color:gray; margin-top:8px; font-size:13px;">Mentions (recent): {card['count']}</p>
                <p style="color:#A9B2BA; font-size:13px;">💡 AI Rationale: {card['explanation']}</p>
                <p style="color:#9AA3AA; font-size:12px; margin-top:6px;">Pos/Neu/Neg: {card['pos']}/{card['neu']}/{card['neg']}</p>
            </div>
            """,
            unsafe_allow_html=True
        )

st.markdown("---")

# === 7. DETAILED VIEW PER PERECHE ===
st.subheader("🔎 Detalii pe pereche")
sel = st.selectbox("Select pair", options=["All"] + pairs, index=0)

def render_items_for_pair(pair_name: str):
    if pair_name == "All":
        df_view = pd.DataFrame(news_items)
    else:
        df_view = pd.DataFrame([n for n in news_items if n["pair"] == pair_name])
    if df_view.empty:
        st.info("No items for this selection.")
        return
    # show selected columns and add link as markdown
    df_view = df_view[["published", "source", "title", "sent_label", "sent_score", "weight", "pair", "link"]]
    df_view = df_view.sort_values(by="published", ascending=False)
    # render as table with clickable links
    for _, row in df_view.iterrows():
        published = row["published"].strftime("%Y-%m-%d %H:%M") if pd.notnull(row["published"]) else "N/A"
        st.markdown(
            f"- **{row['title']}**  \n  Source: *{row['source']}* | Published: {published} | Sentiment: **{row['sent_label']}** ({round(row['sent_score'],3)})  \n  [Open article]({row['link']})"
        )

if sel == "All":
    st.markdown("Showing all recent fetched items (filtered & classified).")
    render_items_for_pair("All")
else:
    st.markdown(f"Showing items classified for **{sel}**")
    render_items_for_pair(sel)

# === 8. ECONOMIC EVENTS (Forex Factory / Calendar) ===
st.markdown("---")
st.subheader("🗓️ Upcoming High & Medium Impact Events (from ForexFactory feed)")
factory_feed = feedparser.parse("https://www.forexfactory.com/ffcal_week_this.xml")
events = []
for entry in factory_feed.entries[:60]:
    title = getattr(entry, "title", "")
    txt = title.lower()
    impact = None
    if "high impact" in txt or "high" in txt and ("impact" in txt or "expected" in txt):
        impact = "🔥 High Impact"
    elif "medium impact" in txt or "medium" in txt:
        impact = "⚠️ Medium Impact"

    if impact:
        published = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published = datetime.datetime.fromtimestamp(time.mktime(entry.published_parsed))
        events.append({
            "Event": title,
            "Impact": impact,
            "Time": published.strftime("%Y-%m-%d %H:%M") if published else "N/A",
            "Link": getattr(entry, "link", "")
        })

if events:
    st.table(pd.DataFrame(events))
else:
    st.info("No upcoming medium/high impact events found in the ForexFactory feed.")

# === FOOTER ===
st.markdown(
    f"<p style='text-align:center; color:gray; font-size:13px;'>Last updated (UTC): "
    f"{datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} | Refresh every 10 min automatically</p>",
    unsafe_allow_html=True
)
