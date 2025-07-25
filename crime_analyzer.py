import os
import feedparser
import requests
import re
import pandas as pd
import streamlit as st
from collections import defaultdict
import plotly.express as px
import spacy
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

# --- Load Env Vars ---
load_dotenv()
DATA_GOV_API_KEY = os.getenv("DATA_GOV_API_KEY")
LOCAL_CSV_DIR = "./"  # folder to scan local CSVs in

# Load spaCy
nlp = spacy.load("en_core_web_sm")

# RSS feeds
RSS_FEEDS = [
    "https://www.latimes.com/california/rss2.0.xml",
    "https://www.crimeinamerica.net/feed/",
    "https://www.themarshallproject.org/rss/recent.rss",
    "https://nypost.com/tag/crime/feed/",
    "https://mylifeofcrime.wordpress.com/feed/",
    "https://cwbchicago.com/feed",
    "https://spdblotter.seattle.gov/feed/",
    "https://www.themarshallproject.org/rss/recent.rss"
]

RACE_KEYWORDS = {
    "Black": ["black", "african-american", "african american"],
    "White": ["white", "caucasian"],
    "Hispanic": ["hispanic", "latino", "latina"],
    "Asian": ["asian", "chinese", "korean", "vietnamese"]
}

# --- Helper functions ---

def fetch_articles():
    articles = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            if not feed.bozo:
                articles.extend(feed.entries)
        except:
            pass
    return articles

def analyze_news_race_mentions(articles):
    counts = defaultdict(int)
    for art in articles:
        text = f"{art.get('title','')} {art.get('summary','')}".lower()
        for race, keywords in RACE_KEYWORDS.items():
            if any(re.search(rf"\b{kw}\b", text) for kw in keywords):
                counts[race] += 1
    return counts

def fetch_fbi_api_estimates():
    try:
        url = "https://api.usa.gov/crime/fbi/sapi/api/estimates/offender/national"
        params = {"api_key": DATA_GOV_API_KEY, "limit": 1000}
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        df = pd.DataFrame(results)
        if "year" not in df.columns or "race" not in df.columns or "offender_count" not in df.columns:
            return None
        df_pivot = df.pivot_table(index="year", columns="race", values="offender_count", aggfunc="sum")
        df_pivot = df_pivot[["White", "Black", "Asian", "Hispanic"]].fillna(0)
        df_percent = (df_pivot.div(df_pivot.sum(axis=1), axis=0) * 100).reset_index()
        return df_percent
    except:
        return None

def load_local_fbi():
    for fname in os.listdir(LOCAL_CSV_DIR):
        if fname.lower().endswith(".csv") and "crime_data" in fname.lower():
            try:
                df = pd.read_csv(os.path.join(LOCAL_CSV_DIR, fname), low_memory=False)
                fmt = "%m/%d/%Y %I:%M:%S %p"
                df["DATE OCC"] = pd.to_datetime(df["DATE OCC"], format=fmt, errors="coerce")
                df = df.dropna(subset=["DATE OCC"])
                df["Year"] = df["DATE OCC"].dt.year
                map_code = {"B": "Black", "W": "White", "H": "Hispanic", "A": "Asian"}
                df["Race"] = df["Vict Descent"].map(map_code)
                df = df.dropna(subset=["Race"])
                counts = df.groupby(["Year", "Race"]).size().unstack(fill_value=0)
                perc = (counts.div(counts.sum(axis=1), axis=0) * 100)[["White", "Black", "Hispanic", "Asian"]].reset_index()
                return perc
            except:
                continue
    return pd.DataFrame()

def load_fbi_data():
    df_api = fetch_fbi_api_estimates()
    if df_api is not None and not df_api.empty:
        return df_api, True
    df_local = load_local_fbi()
    return df_local, False

def compare_disproportion(news_counts, fbi_df):
    total = sum(news_counts.values())
    if total == 0 or fbi_df.empty:
        return {}
    news_pct = {r: (c / total) * 100 for r, c in news_counts.items()}
    latest = fbi_df.iloc[-1]
    dispro = {}
    for r in ["White", "Black", "Hispanic", "Asian"]:
        dispro[r] = news_pct.get(r, 0.1) / max(latest.get(r, 0.1), 0.1)
    return dispro

def get_recent_ckan_datasets():
    try:
        url = "https://catalog.data.gov/api/3/action/package_search"
        headers = {"Authorization": DATA_GOV_API_KEY} if DATA_GOV_API_KEY else {}
        thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S")
        params = {
            "q": "crime OR police",
            "rows": 1348,
            "fq": f"metadata_modified:[{thirty_days_ago}Z TO *]"
        }
        resp = requests.get(url, headers=headers, params=params, timeout=60)
        resp.raise_for_status()
        datasets = resp.json().get("result", {}).get("results", [])
        dfs = []
        for ds in datasets:
            for res in ds.get("resources", []):
                fmt = res.get("format", "").lower()
                name = res.get("name", "").lower()
                if fmt == "csv" and ("crime" in name or "police" in name):
                    try:
                        df = pd.read_csv(res["url"], nrows=10000)
                        dfs.append(df)
                    except Exception as e:
                        st.warning(f"Failed to load CKAN CSV resource {name}: {e}")
        return dfs
    except Exception as e:
        st.warning(f"Failed to fetch CKAN datasets: {e}")
        return []

def get_color_by_ratio(ratio):
    if ratio > 1.5:
        return "#ff4b4b"  # Red (highly overrepresented)
    elif ratio > 1.0:
        return "#f9d71c"  # Yellow (slightly overrepresented)
    else:
        return "#2ecc71"  # Green (underrepresented or equal)

def article_card(title, race_group, ratio, link, explanation):
    color = get_color_by_ratio(ratio)
    st.markdown(
        f"""
        <div style="
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 15px;
            background-color: {color};
            color: black;
            box-shadow: 2px 2px 8px rgba(0,0,0,0.15);
            ">
            <h4 style="margin-bottom:5px;"><a href="{link}" target="_blank" style="color:black; text-decoration:none;">{title}</a></h4>
            <p style="margin:0;"><b>Most Overrepresented Group:</b> {race_group} ({ratio:.2f}x)</p>
            <p style="font-size:12px; color:#333;">Tagging keywords matched: {explanation}</p>
        </div>
        """,
        unsafe_allow_html=True
    )

# --- Streamlit UI ---
st.set_page_config("Crime News Analyzer", layout="wide")
st.title("Crime News vs. FBI & Open Data Crime Sources")

with st.spinner("Fetching news articles..."):
    articles = fetch_articles()
    if not articles:
        st.warning("No news articles fetched.")
        st.stop()
    race_counts = analyze_news_race_mentions(articles)

fbi_df, is_live = load_fbi_data()
dispro = compare_disproportion(race_counts, fbi_df)

ckan_dfs = get_recent_ckan_datasets()

st.subheader("Loaded Recent Open Data (Last 30 Days) from Data.gov")
if ckan_dfs:
    for i, df in enumerate(ckan_dfs[:3]):
        st.write(f"CKAN Dataset #{i+1}")
        st.dataframe(df.head(5))
else:
    st.info("No recent open datasets loaded from Data.gov.")

col1, col2 = st.columns(2)
with col1:
    st.subheader("Race Mentions in Crime News")
    df_news = pd.DataFrame.from_dict(race_counts, orient="index", columns=["Count"])
    st.plotly_chart(px.bar(df_news, title="News Coverage by Race"))

with col2:
    st.subheader(f"FBI Offender Race Distribution by Year ({'Live API' if is_live else 'Local CSV'})")
    st.plotly_chart(px.line(
        fbi_df,
        x="year" if "year" in fbi_df.columns else "Year",
        y=["White", "Black", "Hispanic", "Asian"],
        labels={"value": "Percent", "variable": "Race"},
        title="FBI Offender Race %"
    ))

st.subheader("Disproportionality: News % vs FBI % (Latest Year)")
if dispro:
    df_dis = pd.DataFrame.from_dict(dispro, orient="index", columns=["Ratio"])
    df_dis["Bias"] = df_dis["Ratio"].apply(lambda x: "Overrepresented" if x > 1 else "Underrepresented")
    st.dataframe(df_dis.style.background_gradient(cmap="RdYlGn", subset=["Ratio"]))
else:
    st.info("Disproportionality data could not be computed.")

# Article cards colored by disproportionality with clickable links and keyword explanations
st.subheader("News Articles Colored by Race Group Overrepresentation")
cols_per_row = 3
cols = st.columns(cols_per_row)

for idx, art in enumerate(articles):
    combined_text = f"{art.get('title','')} {art.get('summary','')}".lower()
    mentioned_groups = []
    explanation_parts = []
    for r, kws in RACE_KEYWORDS.items():
        matched = [kw for kw in kws if re.search(rf"\b{kw}\b", combined_text)]
        if matched:
            mentioned_groups.append(r)
            explanation_parts.append(f"{r}: {', '.join(matched)}")

    explanation = "; ".join(explanation_parts) if explanation_parts else "No race keywords found"

    if mentioned_groups:
        ratios = {g: dispro.get(g, 1.0) for g in mentioned_groups}
        top_group = max(ratios, key=ratios.get)
        top_ratio = ratios[top_group]
    else:
        top_group = "None"
        top_ratio = 1.0

    with cols[idx % cols_per_row]:
        article_card(
            art.get("title", "No Title"),
            top_group,
            top_ratio,
            art.get("link", "#"),
            explanation
        )

with st.expander("Debug: Show raw articles and FBI data"):
    if st.checkbox("Show raw news articles"):
        st.write(articles[:3])
    if st.checkbox("Show FBI Data Table"):
        st.write(fbi_df)
