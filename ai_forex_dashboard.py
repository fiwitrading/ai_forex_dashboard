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
with st.expander("Settings (feeds, items per feed, source weights, macro tuning)", True):
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
    st.markdown("Macro tuning:")
    macro_influence = st.slider("Macro influence on bias (gamma)", min_value=0.0, max_value=1.0, value=0.25, step=0.01)
    st.caption("Cât de mult influențează evenimentele macro scorul agregat al perechii (0 = ignoră, 1 = puternic).")

# === RSS FEEDS ===
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
    "EUR/USD": ["eurusd", "euro", "ecb", "eurozone", "european central bank", "eurostat", "bundesbank", "eur"],
    "GBP/USD": ["gbpusd", "pound", "sterling", "bank of england", "boe", "uk", "britain", "gbp"],
    "USD/JPY": ["usdjpy", "yen", "boj", "bank of japan", "tokyo", "japan", "jpy"],
    "XAU/USD": ["gold", "xau", "spot gold", "precious metal", "gold price", "xauusd"],
}
PAIR_LABELS = list(PAIR_KEYWORDS.keys())

# Pair base/quote mapping
PAIR_BASE_QUOTE = {
    "EUR/USD": ("EUR", "USD"),
    "GBP/USD": ("GBP", "USD"),
    "USD/JPY": ("USD", "JPY"),
    "XAU/USD": ("XAU", "USD")
}

# === MACRO EVENT KEYWORDS ===
MACRO_KEYWORDS = {
    "cpi": "USD",
    "consumer price": "USD",
    "inflation": "USD",
    "nfp": "USD",
    "nonfarm": "USD",
    "unemployment": "USD",
    "jobs report": "USD",
    "gdp": "USD",
    "fed": "USD",
    "fomc": "USD",
    "interest rate": "USD",
    "rate decision": "USD",
    "ecb": "EUR",
    "euro area": "EUR",
    "bank of england": "GBP",
    "boj": "JPY",
    "japan": "JPY",
    "uk": "GBP",
    "britain": "GBP",
    "pound": "GBP"
}

POSITIVE_SIGNS = [
    "beats", "better than expected", "strong", "stronger", "tops expectations", "higher than expected",
    "surprise up", "revised up", "rise", "risen", "upbeat", "positive", "hike", "raises", "raised", "rate hike", "increases"
]
NEGATIVE_SIGNS = [
    "misses", "below expectations", "weaker", "lower than expected", "disappoint", "falls", "fell", "down", "cut", "cuts", "cut rates", "eases", "negative", "revised down"
]

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

# Load pipelines
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
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published = datetime.datetime.fromtimestamp(time.mktime(entry.published_parsed))
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                published = datetime.datetime.fromtimestamp(time.mktime(entry.updated_parsed))
            elif hasattr(entry, "published"):
                try:
                    published = pd.to_datetime(entry.published).to_pydatetime()
                except Exception:
                    published = None

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

for n in news_items:
    combined = f"{n['title']} . {n['summary']}"
    n["text"] = combined
    pair = match_pair_by_keywords(combined)
    n["pair"] = pair if pair else "Other"

# Zero-shot classification for unmatched items
unmatched = [n for n in news_items if n["pair"] == "Other"]
if zero_shot and len(unmatched) > 0:
    try:
        texts = [u["text"] for u in unmatched]
        z_results = zero_shot(texts, PAIR_LABELS, multi_label=False)
        if isinstance(z_results, dict):
            z_results = [z_results]
        for u, res in zip(unmatched, z_results):
            label = res["labels"][0]
            score = res["scores"][0]
            if score >= 0.3:
                u["pair"] = label
    except Exception:
        pass

# === 3. MACRO EVENT DETECTION ===
def detect_macro_events_in_text(text: str) -> List[Dict]:
    t = text.lower()
    found = []
    for kw, cur in MACRO_KEYWORDS.items():
        if kw in t:
            signal = 0.0
            for pw in POSITIVE_SIGNS:
                if pw in t:
                    signal += 1.0
            for nw in NEGATIVE_SIGNS:
                if nw in t:
                    signal -= 1.0
            if signal > 0:
                signal = min(1.0, signal)
            elif signal < 0:
                signal = max(-1.0, signal)
            else:
                signal = 0.25
            found.append({"event": kw, "currency": cur, "signal": signal})
    return found

for n in news_items:
    n["macro_events"] = detect_macro_events_in_text(n["text"])

# Parse ForexFactory calendar entries to augment macro events
try:
    factory_feed = feedparser.parse("https://www.forexfactory.com/ffcal_week_this.xml")
    for entry in factory_feed.entries[:80]:
        title = getattr(entry, "title", "") or ""
        txt = title.lower()
        matched = any(kw in txt for kw in MACRO_KEYWORDS.keys())
        if matched:
            events = detect_macro_events_in_text(txt)
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published = datetime.datetime.fromtimestamp(time.mktime(entry.published_parsed))
            news_items.append({
                "source": "Forex Factory (calendar)",
                "title": title,
                "summary": "",
                "link": getattr(entry, "link", ""),
                "published": published,
                "text": txt,
                "pair": "Other",
                "macro_events": events
            })
except Exception:
    pass

# === 4. SENTIMENT ANALYSIS (batch) ===
texts = [n["title"] for n in news_items]
sent_results = []
try:
    sent_results = sentiment_pipeline(texts, truncation=True)
except Exception:
    # fallback: single calls
    for t in texts:
        try:
            r = sentiment_pipeline(t)
            sent_results.append(r)
        except Exception:
            sent_results.append([{"label": "NEUTRAL", "score": 0.5}])

def sentiment_to_numeric(label: str) -> float:
    lab = label.lower()
    if "positive" in lab or "pos" in lab:
        return 1.0
    if "negative" in lab or "neg" in lab:
        return 0.0
    return 0.5

for n, s in zip(news_items, sent_results):
    if isinstance(s, list):
        s = s[0]
    label = s.get("label", "") if isinstance(s, dict) else ""
    score = float(s.get("score", 0.0)) if isinstance(s, dict) else 0.0
    n["sent_label"] = label
    n["sent_score"] = score
    n["sent_value"] = sentiment_to_numeric(label)

# === 5. WEIGHTING: recency and source weight ===
def recency_weight(published: datetime.datetime, half_life_hours: float) -> float:
    if published is None:
        return 0.2
    age_hours = max((now - published).total_seconds() / 3600.0, 0.0)
    lam = - (1.0 / half_life_hours) * 0.693147
    weight = exp(lam * age_hours)
    return weight

for n in news_items:
    src_w = source_weights.get(n["source"], source_weights.get("Default", 1.0))
    r_w = recency_weight(n.get("published"), recency_half_life_hours)
    n["weight"] = src_w * r_w

# === 6. AGGREGARE PER PERECHE + APLICARE EFECT MACRO ===
pairs = PAIR_LABELS.copy()
agg = {}
for p in pairs:
    items = [n for n in news_items if n["pair"] == p]
    if not items:
        agg[p] = {
            "count": 0,
            "weighted_score": 0.5,
            "adjusted_score": 0.5,
            "bias": "Neutral",
            "color": "#D4D4D4",
            "top_titles": [],
            "pos": 0, "neu": 0, "neg": 0,
            "explanation": "No recent news matched this pair.",
            "macro_effect": 0.0,
            "macro_events": []
        }
        continue

    weighted_sum = sum(n["sent_value"] * n["weight"] for n in items)
    total_w = sum(n["weight"] for n in items) or 1.0
    weighted_score = weighted_sum / total_w

    pos = sum(1 for n in items if n["sent_value"] > 0.75)
    neu = sum(1 for n in items if 0.4 <= n["sent_value"] <= 0.75)
    neg = sum(1 for n in items if n["sent_value"] < 0.4)

    sorted_items = sorted(items, key=lambda x: x.get("weight", 0.0) * x.get("sent_score", 0.0), reverse=True)
    top_titles = [{
        "title": s["title"],
        "link": s["link"],
        "source": s["source"],
        "published": s["published"].strftime("%Y-%m-%d %H:%M") if pd.notnull(s.get("published")) else "N/A",
        "sent_label": s.get("sent_label", ""),
        "sent_score": round(s.get("sent_score", 0.0), 3),
        "weight": round(s.get("weight", 0.0), 3)
    } for s in sorted_items[:5]]

    explanation = ""
    if summarizer and len(sorted_items) > 0:
        try:
            concat = " ".join(t["title"] for t in sorted_items[:6])
            summary = summarizer(concat, max_length=50, min_length=15, do_sample=False)[0]["summary_text"]
            explanation = summary
        except Exception:
            explanation = sorted_items[0]["title"]
    else:
        explanation = sorted_items[0]["title"]

    # MACRO EFFECTS
    macro_effect_sum = 0.0
    macro_events_list = []
    for n in items:
        for ev in n.get("macro_events", []):
            cur = ev.get("currency")
            signal = ev.get("signal", 0.0)
            base, quote = PAIR_BASE_QUOTE.get(p, (None, None))
            if base is None or quote is None:
                continue
            effect_on_pair = 0.0
            if cur == base:
                effect_on_pair = signal
            elif cur == quote:
                effect_on_pair = -signal
            else:
                effect_on_pair = 0.0
            macro_effect_sum += effect_on_pair * n.get("weight", 1.0)
            if abs(signal) > 0:
                macro_events_list.append({
                    "title": n["title"],
                    "event": ev.get("event"),
                    "currency": cur,
                    "signal": signal,
                    "weight": n.get("weight", 1.0),
                    "published": n.get("published")
                })

    macro_effect_norm = macro_effect_sum / (total_w or 1.0)

    adjusted_score = weighted_score + macro_influence * macro_effect_norm
    adjusted_score = max(0.0, min(1.0, adjusted_score))

    if adjusted_score >= 0.62:
        bias = "Bullish"
        color = "#16C47F"
    elif adjusted_score <= 0.38:
        bias = "Bearish"
        color = "#D44D5C"
    else:
        bias = "Neutral"
        color = "#D4D4D4"

    agg[p] = {
        "count": len(items),
        "weighted_score": round(weighted_score, 3),
        "adjusted_score": round(adjusted_score, 3),
        "bias": bias,
        "color": color,
        "top_titles": top_titles,
        "pos": pos, "neu": neu, "neg": neg,
        "explanation": explanation,
        "macro_effect": round(macro_effect_norm, 4),
        "macro_events": macro_events_list
    }

# === 7. UI: Cards with macro info ===
cols = st.columns(len(pairs))
for i, p in enumerate(pairs):
    card = agg[p]
    with cols[i]:
        st.markdown(
            f"""
            <div style="background-color:#0C0F11; padding:15px; border-radius:12px; border:1px solid #1E242A; min-height:220px;">
                <h3 style="color:white; text-align:center;">{p}</h3>
                <h4 style="color:{card['color']}; text-align:center;">{card['bias']} ({int(card['adjusted_score']*100)}%)</h4>
                <div style="background:#1E242A; border-radius:10px; height:12px; margin-bottom:8px;">
                    <div style="width:{int(card['adjusted_score']*100)}%; background:{card['color']}; height:12px; border-radius:10px;"></div>
                </div>
                <p style="color:gray; margin-top:4px; font-size:13px;">Mentions (recent): {card['count']}</p>
                <p style="color:#A9B2BA; font-size:13px;">💡 AI Rationale: {card['explanation']}</p>
                <p style="color:#9AA3AA; font-size:12px; margin-top:6px;">Pos/Neu/Neg: {card['pos']}/{card['neu']}/{card['neg']}</p>
                <p style="color:#9AA3AA; font-size:12px; margin-top:6px;">Macro effect: {card['macro_effect']}</p>
            </div>
            """,
            unsafe_allow_html=True
        )

st.markdown("---")

# === 8. DETAILED VIEW PER PERECHE ===
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
    df_view = df_view[["published", "source", "title", "sent_label", "sent_score", "weight", "pair", "link", "macro_events"]]
    df_view = df_view.sort_values(by="published", ascending=False)
    for _, row in df_view.iterrows():
        published = row["published"].strftime("%Y-%m-%d %H:%M") if pd.notnull(row["published"]) else "N/A"
        macro_events = row["macro_events"] if isinstance(row["macro_events"], list) else []
        macro_str = ""
        if macro_events:
            macro_parts = []
            for me in macro_events:
                if isinstance(me, dict):
                    macro_parts.append(f"{me.get('event')} ({me.get('currency')}: {me.get('signal')})")
            macro_str = " | Macro: " + ", ".join(macro_parts)
        st.markdown(
            f"- **{row['title']}**  \n  Source: *{row['source']}* | Published: {published} | Sentiment: **{row['sent_label']}** ({round(row['sent_score'],3)})  {macro_str}  \n  [Open article]({row['link']})"
        )

if sel == "All":
    st.markdown("Showing all recent fetched items (filtered & classified).")
    render_items_for_pair("All")
else:
    st.markdown(f"Showing items classified for **{sel}**")
    render_items_for_pair(sel)

# === 9. ECONOMIC EVENTS (Forex Factory / Calendar) ===
st.markdown("---")
st.subheader("🗓️ Upcoming High & Medium Impact Events (from ForexFactory feed)")
events = []
try:
    factory_feed = feedparser.parse("https://www.forexfactory.com/ffcal_week_this.xml")
    for entry in factory_feed.entries[:60]:
        title = getattr(entry, "title", "") or ""
        txt = title.lower()
        impact = None
        if "high impact" in txt or ("high" in txt and ("impact" in txt or "expected" in txt)):
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
except Exception:
    pass

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
