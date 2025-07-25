## Crime Analyzer
### Used for comparing RSS feeds from news networks then identifying race based data and comparing with actual FBI crime data to understand if news media is under or over reporting on marginalized minority groups to give a false sense of who is commiting the crime in local and regional areas. This is ment to compare geolocations of crime and news.

### Create virtual environment (python3 -m venv env_name)
```python3 -m venv crime_analyzer_env```

### Activate the environment
```source crime_analyzer_env/bin/activate```

### Install pip3 packages
``` pip3 install feedparser requests pandas streamlit plotly python-dotenv```


### run command locally to test

```streamlit run crime_analyzer.py```

URL : https://crimeanalyzer.streamlit.app
