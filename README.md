# Streamlit Dashboard

This folder contains an independent Streamlit version of the dashboard.
The original React/Vite version remains in `../Дашборд`.

## Run locally

```bash
cd streamlit_dashboard
python -m pip install -r requirements.txt
streamlit run app.py
```

## Data source

Default file path used by the app:

- `data/dashboard_data.xlsx`

You can replace this file with a newer Excel export that keeps the same structure.
You can also upload an `.xlsx` directly from the sidebar while the app is running.
