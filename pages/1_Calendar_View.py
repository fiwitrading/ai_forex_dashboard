import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
import requests
import feedparser

# === CONFIGURARE PAGINĂ ===
st.set_page_config(page_title="Economic Calendar", layout="wide")
st.title("🗓️ Economic Calendar")
st.caption("Data sources: ForexFactory • Investing.com • DailyFX — updated automatically")

# === FUNCȚIE CONVERSIE ORĂ ===
def convert_to_local_time(utc_time_str, target_tz="Europe/Bucharest"):
    try:
        utc_dt = datetime.strptime(utc_time_str, "%a, %d %b %Y %H:%M:%S %z")
        local_dt = utc_dt.astimezone(pytz.timezone(target_tz))
        return local_dt.strftime("%d %b %Y, %H:%M")
    except Exception:
        return "N/A"

# === 1️⃣ FETCH MULTIPLE FEEDS ===
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
feeds = {
    "ForexFactory": "https://www.forexfactory.com/ffcal_week_this.xml",
    "Investing.com": "https://www.investing.com/rss/news_301.rss",
    "DailyFX": "https://www.dailyfx.com/feeds/all",
}

events = []

for source, url in feeds.items():
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        feed = feedparser.parse(response.text)
        for entry in feed.entries[:15]:
            title = entry.title
            published = getattr(entry, "published", "N/A")
            impact = "Low"

            title_lower = title.lower()
            if "high impact" in title_lower:
                impact = "High"
            elif "medium impact" in title_lower:
                impact = "Medium"
            elif "low impact" in title_lower:
                impact = "Low"

            if "usd" in title_lower:
                country = "🇺🇸 USD"
            elif "eur" in title_lower:
                country = "🇪🇺 EUR"
            elif "gbp" in title_lower:
                country = "🇬🇧 GBP"
            elif "jpy" in title_lower:
                country = "🇯🇵 JPY"
            elif "cad" in title_lower:
                country = "🇨🇦 CAD"
            elif "aud" in title_lower:
                country = "🇦🇺 AUD"
            elif "chf" in title_lower:
                country = "🇨🇭 CHF"
            elif "cny" in title_lower:
                country = "🇨🇳 CNY"
            else:
                country = "🌍 Other"

            events.append({
                "Time (local)": convert_to_local_time(published),
                "Country": country,
                "Impact": impact,
                "Event": title.replace("High Impact Expected", "")
                              .replace("Medium Impact Expected", "")
                              .replace("Low Impact Expected", "")
                              .strip(),
                "Source": source
            })
    except Exception as e:
        st.warning(f"⚠️ {source} feed unavailable: {e}")

# === 2️⃣ VERIFICARE ===
if len(events) == 0:
    st.error("No data fetched from any source. Try again later.")
    st.stop()

# === 3️⃣ TRANSFORMARE ÎN DATAFRAME ===
df = pd.DataFrame(events)

# === 4️⃣ FILTRE ===
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

# === 5️⃣ APLICARE FILTRE ===
filtered_df = df[
    (df["Impact"].isin(impact_filter)) &
    (df["Country"].isin(country_filter)) &
    (df["Source"].isin(source_filter))
]

filtered_df = filtered_df.sort_values(by="Time (local)", ascending=True)

# === 6️⃣ STILIZARE ===
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

# === 7️⃣ BUTON REFRESH ===
if st.button("🔄 Refresh Calendar"):
    st.rerun()
