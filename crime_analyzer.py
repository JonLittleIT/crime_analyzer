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

# --- Load Env Vars ---
load_dotenv()
API_KEY = os.getenv("API_KEY")  # from api.data.gov
LOCAL_CSV_FILE = "Crime_Data_from_2020_to_Present.csv"

# Load spaCy (for potential NLP expansions)
nlp = spacy.load("en_core_web_sm")

# RSS feeds to fetch crime news from
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

# Keyword race mapping
RACE_KEYWORDS = {
    "Black": ["black", "african-american", "african american"],
    "White": ["white", "caucasian"],
    "Hispanic": ["hispanic", "latino", "latina"],
    "Asian": ["asian", "chinese", "korean", "vietnamese"]
}

# --- Functions ---

def fetch_articles():
    articles = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            if not feed.bozo:
                articles.extend(feed.entries)
        except:
            pass  # Silent fail
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
    if not API_KEY:
        return None
    try:
        url = "https://api.usa.gov/crime/fbi/sapi/api/estimates/offender/national"
        params = {"api_key": API_KEY, "limit": 1000}
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
    try:
        df = pd.read_csv(LOCAL_CSV_FILE, low_memory=False)
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

# --- Streamlit UI ---

st.set_page_config("Crime News Analyzer", layout="wide")
st.title("Crime News vs. FBI Crime Data (Live & Local)")

with st.spinner("Fetching articles..."):
    articles = fetch_articles()
    if not articles:
        st.warning("No news articles could be fetched at this time.")
        st.stop()
    race_counts = analyze_news_race_mentions(articles)

fbi_df, is_live = load_fbi_data()

dispro = compare_disproportion(race_counts, fbi_df)

col1, col2 = st.columns(2)

with col1:
    st.subheader("Race Mentions in Crime News")
    df_news = pd.DataFrame.from_dict(race_counts, orient="index", columns=["Count"])
    if not df_news.empty:
        st.plotly_chart(px.bar(df_news, title="News Coverage by Race"))

with col2:
    st.subheader(f"FBI Offender Race Distribution by Year ({'Live API' if is_live else 'Local CSV'})")
    if not fbi_df.empty:
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

# Optional Debugging UI
with st.expander("Debug: Show raw articles and FBI data"):
    if st.checkbox("Show raw news articles"):
        st.write(articles[:3])
    if st.checkbox("Show FBI Data Table"):
        st.write(fbi_df)
