## Crime Analyzer

### Used for comparing RSS feeds from news networks then identifying race based data and comparing with actual FBI crime data to understand if news media is under or over reporting on marginalized minority groups to give a false sense of who is commiting the crime in local and regional areas. This is ment to compare geolocations of crime and news.

You must requeset a data API key if you dont only want to use local .csv for data sets. The code is built to use .csv if the API fails so it can gracefully report on local .csv files and not just load nothing with out internet.

[https://data.gov/user-guide/](https://data.gov/user-guide/)

[https://docs.ckan.org/en/2.11/api/index.html]([https://docs.ckan.org/en/2.11/api/index.html]())

---

### Create virtual environment (python3 -m venv env_name)

``python3 -m venv crime_analyzer_env``

### Activate the environment

``source crime_analyzer_env/bin/activate``

### Install pip3 packages

`` pip3 install feedparser requests pandas streamlit plotly python-dotenv``

### run command locally to test

``streamlit run crime_analyzer.py``

example site (free version) : [https://crimeanalyzer.streamlit.app](https://crimeanalyzer.streamlit.app)
