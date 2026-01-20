import streamlit as st
import feedparser
import pandas as pd
from datetime import datetime
import pytz

# === CONFIGURARE PAGINĂ ===
st.set_page_config(page_title="Economic Calendar", layout="wide")
st.title("🗓️ Economic Calendar")
st.caption("Date source: ForexFactory — Updated automatically")

# === FUNCTIE DE CONVERSIE TIMEZONE ===
def convert_to_local_time(utc_time_str, target_tz="Europe/Bucharest"):
    try:
        utc_dt = datetime.strptime(utc_time_str, "%a, %d %b %Y %H:%M:%S %z")
        local_dt = utc_dt.astimezone(pytz.timezone(target_tz))
        return local_dt.strftime("%d %b %Y, %H:%M")
    except Exception:
        return "N/A"

# === PRELUARE FEED FOREX FACTORY ===
feed_url = "https://www.forexfactory.com/ffcal_week_this.xml"
feed = feedparser.parse(feed_url)

events = []
for entry in feed.entries:
    title = entry.title
    published = getattr(entry, "published", "N/A")
    impact = "Low"

    title_lower = title.lower()
    if "high impact" in title_lower:
        impact = "High"
    elif "medium impact" in title_lower:
        impact = "Medium"

    # Țara (simplificat după abreviere)
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
    else:
        country = "🌍 Other"

    events.append({
        "Time (local)": convert_to_local_time(published),
        "Country": country,
        "Impact": impact,
        "Event": title.replace("High Impact Expected", "").replace("Medium Impact Expected", "").replace("Low Impact Expected", "").strip()
    })

# === TRANSFORMARE ÎN DATAFRAME ===
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

# === APLICARE FILTRE ===
filtered_df = df[
    (df["Impact"].isin(impact_filter)) &
    (df["Country"].isin(country_filter))
]

# === SORTARE DUPĂ TIMP ===
filtered_df = filtered_df.sort_values(by="Time (local)", ascending=True)

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
    height=600
)

# === REFRESH BUTTON ===
if st.button("🔄 Refresh Calendar"):
    st.rerun()

