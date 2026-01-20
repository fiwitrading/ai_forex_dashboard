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
# Recomandare: mută cheia în st.secrets['NEWSDATA_API_KEY']
API_KEY = st.secrets.get("NEWSDATA_API_KEY", "pub_509adedfa35443b3aac899dc0fcd9f14")
BASE_URL = "https://newsdata.io/api/1/news"

# === FUNCTIE CONVERSIE ORĂ (mai tolerantă) ===
def convert_to_local_time(utc_time_value, target_tz="Europe/Bucharest"):
    try:
        if not utc_time_value:
            return "N/A"

        # Dacă e deja datetime
        if isinstance(utc_time_value, datetime):
            utc_dt = utc_time_value
            if utc_dt.tzinfo is None:
                utc_dt = pytz.utc.localize(utc_dt)
        else:
            # Folosim pandas pentru parsing tolerant la formate diferite
            utc_dt = pd.to_datetime(utc_time_value, utc=True, errors="coerce")
            if pd.isna(utc_dt):
                # încercare fallback: înlăturăm T și Z
                s = str(utc_time_value).replace("T", " ").replace("Z", "")
                utc_dt = pd.to_datetime(s, errors="coerce")
                if pd.isna(utc_dt):
                    return "N/A"
                try:
                    utc_dt = utc_dt.tz_localize(pytz.utc)
                except Exception:
                    utc_dt = pd.to_datetime(utc_dt).tz_localize(pytz.utc)

        local_dt = utc_dt.astimezone(pytz.timezone(target_tz))
        return local_dt.strftime("%d %b %Y, %H:%M")
    except Exception:
        return "N/A"

# === BUILD QUERY & PARAMS ===
query = "economy OR inflation OR interest rates OR forex OR central bank OR CPI OR GDP OR unemployment"
base_params = {
    "apikey": API_KEY,
    "language": "en",
    "q": query,
    "category": "business,world,economy"
}

st.info("Fetching latest economic headlines...")

def try_request(params):
    try:
        resp = requests.get(BASE_URL, params=params, timeout=15)
    except Exception as e:
        st.error(f"Network error when calling NewsData: {e}")
        return None, None
    content = None
    try:
        content = resp.json()
    except Exception:
        content = resp.text
    return resp, content

# 1) Prima încercare: params inițiali
resp, content = try_request(base_params)
data = None

# 2) Tratare răspuns / fallback-uri
if resp is None:
    st.stop()

if resp.status_code != 200:
    # Afișăm mesajul serverului (json sau text) pentru debugging
    st.error(f"NewsData API returned status {resp.status_code}: {content}")

    # Dacă 422 sau altă eroare de validare, încercăm fallback-uri
    if resp.status_code == 422:
        st.info("Attempting fallback: retrying without 'category' parameter...")
        params_no_category = base_params.copy()
        params_no_category.pop("category", None)
        resp2, content2 = try_request(params_no_category)
        if resp2 is not None and resp2.status_code == 200:
            data = content2
        else:
            st.error(f"Fallback without category returned status {getattr(resp2, 'status_code', 'N/A')}: {content2}")
            st.info("Attempting second fallback: simplified query 'economy' ...")
            params_simple_q = base_params.copy()
            params_simple_q.pop("category", None)
            params_simple_q["q"] = "economy"
            resp3, content3 = try_request(params_simple_q)
            if resp3 is not None and resp3.status_code == 200:
                data = content3
            else:
                st.error(f"Simplified query fallback returned status {getattr(resp3, 'status_code', 'N/A')}: {content3}")
                st.stop()
    else:
        # alte coduri (401,403,429,500 etc.) — oprim după afișare
        st.stop()
else:
    data = content

# În continuare, 'data' ar trebui să fie dict-ul JSON returnat de API
if not data or "results" not in data:
    st.error("No results found in API response or unexpected format. See previous errors above for details.")
    st.stop()

# === PROCESARE RESULTS ===
events = []
for idx, item in enumerate(data["results"]):
    # Protecție: unele elemente pot fi None / string etc.
    if not isinstance(item, dict):
        st.warning(f"Skipping unexpected result at index {idx} (not a dict).")
        continue

    title = item.get("title") or item.get("headline") or "No title"
    source = item.get("source_id") or item.get("source") or "Unknown"

    # unele API-uri pot folosi chei diferite pentru dată -> încercăm mai multe variante
    pub_date_raw = item.get("pubDate") or item.get("pub_date") or item.get("pubdate") or ""

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
        "Time (local)": convert_to_local_time(pub_date_raw),
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

currency_options = sorted(df["Currency"].unique()) if not df.empty else []
currency_filter = st.sidebar.multiselect(
    "Select currencies:",
    options=currency_options,
    default=currency_options
)

filtered_df = df[
    (df["Impact"].isin(impact_filter)) &
    (df["Currency"].isin(currency_filter))
] if not df.empty else df

# sortare: dacă coloana "Time (local)" are valori "N/A", le punem la final
def sort_time_safe(df_in):
    if "Time (local)" not in df_in.columns or df_in.empty:
        return df_in
    times = pd.to_datetime(df_in["Time (local)"], format="%d %b %Y, %H:%M", errors="coerce")
    return df_in.assign(_sort_time=times).sort_values(by="_sort_time", ascending=False).drop(columns=["_sort_time"])

filtered_df = sort_time_safe(filtered_df)

# === STILIZARE ===
def color_impact(val):
    if val == "High":
        color = "#D44D5C"
    elif val == "Medium":
        color = "#E6B800"
    else:
        color = "#16C47F"
    return f"color: {color}; font-weight: bold;"

if not filtered_df.empty:
    st.dataframe(
        filtered_df.style.applymap(color_impact, subset=["Impact"]),
        use_container_width=True,
        height=650
    )
else:
    st.info("No events to display with current filters.")

# === REZUMAT SUS ===
st.markdown("---")
st.subheader("📊 Summary of current news bias")
count_high = len(df[df["Impact"] == "High"])
count_medium = len(df[df["Impact"] == "Medium"])
count_low = len(df[df["Impact"] == "Low"])

top_currency = df["Currency"].value_counts().idxmax() if not df.empty else "N/A"

st.write(
    f"**High Impact:** {count_high} | **Medium:** {count_medium} | **Low:** {count_low} | "
    f"**Most Active Currency:** {top_currency}"
)

# === BUTON REFRESH ===
if st.button("🔄 Refresh Data"):
    st.experimental_rerun()
