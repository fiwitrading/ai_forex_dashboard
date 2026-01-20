import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
import requests
import feedparser

# === CONFIGURARE PAGINĂ ===
st.set_page_config(page_title="Economic Calendar", layout="wide")
st.title("🗓️ Economic Calendar")
st.caption("Data sources: TradingEconomics • Investing.com • FXStreet — updated automatically")

# === FUNCȚIE CONVERSIE ORĂ ===
def convert_to_local_time(utc_time_str, target_tz="Europe/Bucharest"):
    try:
        utc_dt = datetime.strptime(utc_time_str, "%a, %d %b %Y %H:%M:%S %z")
        local_dt = utc_dt.astimezone(pytz.timezone(target_tz))
        return local_dt.strftime("%d %b %Y, %H:%M")
    except Exception:
        return "N/A"

# === SURSE FUNCȚIONALE ===
feeds = {
    "TradingEconomics": "https://tradingeconomics.com/rss/news.aspx?g=all",
    "Investing.com": "https://www.investing.com/rss/news_301.rss",
    "FXStreet": "https://www.fxstreet.com/rss/news",
}

headers = {"User-Agent": "Mozilla/5.0"}
events = []

for source, url in feeds.items():
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        feed = feedparser.parse(response.text)
        for entry in feed.entries[:20]:
            title = entry.title
            published = getattr(entry, "published", "N/A")
            impact = "Medium"

            title_lower = title.lower()
            if any(x in title_lower for x in ["high impact", "rate decision", "inflation", "cpi", "gdp", "nfp"]):
                impact = "High"
            elif any(x in title_lower for x in ["medium", "manufacturing", "retail", "survey"]):
                impact = "Medium"
            else:
                impact = "Low"

            if "usd" in title_lower or "us" in title_lower or "fed" in title_lower:
                country = "🇺🇸 USD"
            elif "eur" in title_lower or "euro" in title_lower or "ecb" in title_lower:
                country = "🇪🇺 EUR"
            elif "gbp" in title_lower or "boe" in title_lower or "uk" in title_lower or "british" in title_lower:
                country = "🇬🇧 GBP"
            elif "jpy" in title_lower or "yen" in title_lower or "boj" in title_lower:
                country = "🇯🇵 JPY"
            elif "cad" in title_lower or "canada" in title_lower:
                country = "🇨🇦 CAD"
            elif "aud" in title_lower or "australia" in title_lower:
                country = "🇦🇺 AUD"
            elif "chf" in title_lower or "swiss" in title_lower:
                country = "🇨🇭 CHF"
            elif "cny" in title_lower or "china" in title_lower:
                country = "🇨🇳 CNY"
            elif "gold" in title_lower or "xau" in title_lower:
                country = "🥇 XAU"
            else:
                country = "🌍 Other"

            events.append({
                "Time (local)": convert_to_local_time(published),
                "Country": country,
                "Impact": impact,
                "Event": title.strip(),
                "Source": source
            })
    except Exception as e:
        st.warning(f"⚠️ {source} feed unavailable: {e}")

# === VERIFICARE ===
if len(events) == 0:
    st.error("No data fetched from available sources. Try again later.")
    st.stop()

# === DATAFRAME ===
df = pd.DataFrame(events)

# === FILTRE ===
st.sidebar.header("⚙️ Filters")

impact_filter = st.sidebar.multiselect(
    "Select impact level:",
    options=["High", "Medium", "Low"],
    default=["High", "Medium"]
)

country_filter = st.sidebar.multiselect(
    "Select countries:",
    options=sorted(df["Country"].unique()),
    default=sorted(df["Country"].unique())
)

source_filter = st.sidebar.multiselect(
    "Select news sources:",
    options=sorted(df["Source"].unique()),
    default=sorted(df["Source"].unique())
)

filtered_df = df[
    (df["Impact"].isin(impact_filter)) &
    (df["Country"].isin(country_filter)) &
    (df["Source"].isin(source_filter))
]

filtered_df = filtered_df.sort_values(by="Time (local)", ascending=True)

# === CULOARE IMPACT ===
def color_impact(val):
    if val == "High":
        color = "#D44D5C"
    elif val == "Medium":
        color = "#E6B800"
    else:
        color = "#16C47F"
    return f"color: {color}; font-weight: bold;"

st.dataframe(
    filtered_df.style.applymap(color_impact, subset=["Impact"]),
    use_container_width=True,
    height=650
)

if st.button("🔄 Refresh Calendar"):
    st.rerun()

