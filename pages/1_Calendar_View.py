import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import pytz

# === CONFIGURARE PAGINĂ ===
st.set_page_config(page_title="Economic Calendar", layout="wide")
st.title("🗓️ Economic News Calendar (AI Source: NewsData.io)")
st.caption("Live macroeconomic headlines classified by impact and currency relevance")

# === API CONFIG ===
API_KEY = "pub_509adedfa35443b3aac899dc0fcd9f14"
BASE_URL = "https://newsdata.io/api/1/news"

# === FUNCTIE CONVERSIE ORĂ ===
def convert_to_local_time(utc_time_str, target_tz="Europe/Bucharest"):
    try:
        utc_dt = datetime.strptime(utc_time_str, "%Y-%m-%d %H:%M:%S")
        local_dt = utc_dt.replace(tzinfo=pytz.utc).astimezone(pytz.timezone(target_tz))
        return local_dt.strftime("%d %b %Y, %H:%M")
    except Exception:
        return "N/A"

# === FETCH ȘTIRI ===
query = "economy OR inflation OR interest rates OR forex OR central bank OR CPI OR GDP OR unemployment"
params = {
    "apikey": API_KEY,
    "language": "en",
    "q": query,
    "category": "business,world,economy"
}

st.info("Fetching latest economic headlines...")

try:
    response = requests.get(BASE_URL, params=params, timeout=15)
    data = response.json()
except Exception as e:
    st.error(f"Error fetching data: {e}")
    st.stop()

if "results" not in data or len(data["results"]) == 0:
    st.error("No data fetched from NewsData.io. Try again later.")
    st.stop()

# === PROCESARE ===
events = []
for item in data["results"]:
    title = item.get("title", "No title")
    source = item.get("source_id", "Unknown")
    pub_date = item.get("pubDate", "").replace("T", " ").replace("Z", "")

    title_lower = title.lower()
    impact = "Low"
    if any(k in title_lower for k in ["interest rate", "inflation", "cpi", "gdp", "nfp", "employment", "rate decision", "central bank"]):
        impact = "High"
    elif any(k in title_lower for k in ["manufacturing", "survey", "retail", "growth", "market sentiment"]):
        impact = "Medium"

    if any(k in title_lower for k in ["usd", "dollar", "federal", "fed", "america"]):
        country = "🇺🇸 USD"
    elif any(k in title_lower for k in ["eur", "euro", "ecb", "europe"]):
        country = "🇪🇺 EUR"
    elif any(k in title_lower for k in ["gbp", "pound", "boe", "uk", "british"]):
        country = "🇬🇧 GBP"
    elif any(k in title_lower for k in ["jpy", "yen", "boj", "japan"]):
        country = "🇯🇵 JPY"
    elif any(k in title_lower for k in ["gold", "xau"]):
        country = "🥇 XAU"
    else:
        country = "🌍 Other"

    events.append({
        "Time (local)": convert_to_local_time(pub_date),
        "Currency": country,
        "Impact": impact,
        "Headline": title,
        "Source": source
    })

df = pd.DataFrame(events)

# === FILTRE ===
st.sidebar.header("⚙️ Filters")
impact_filter = st.sidebar.multiselect(
    "Select impact level:",
    options=["High", "Medium", "Low"],
    default=["High", "Medium"]
)
currency_filter = st.sidebar.multiselect(
    "Select currencies:",
    options=sorted(df["Currency"].unique()),
    default=sorted(df["Currency"].unique())
)

filtered_df = df[
    (df["Impact"].isin(impact_filter)) &
    (df["Currency"].isin(currency_filter))
]

filtered_df = filtered_df.sort_values(by="Time (local)", ascending=False)

# === STILIZARE ===
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

# === REZUMAT SUS ===
st.markdown("---")
st.subheader("📊 Summary of current news bias")
count_high = len(df[df["Impact"] == "High"])
count_medium = len(df[df["Impact"] == "Medium"])
count_low = len(df[df["Impact"] == "Low"])

top_currency = df["Currency"].value_counts().idxmax()

st.write(
    f"**High Impact:** {count_high} | **Medium:** {count_medium} | **Low:** {count_low} | "
    f"**Most Active Currency:** {top_currency}"
)

# === BUTON REFRESH ===
if st.button("🔄 Refresh Data"):
    st.rerun()
