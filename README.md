# Sensing Engine Backend

FastAPI service for the Sensing Engine dashboard. It reads local sales-history and social-signal datasets to provide forecast, trend, SKU-mapping, signal, and health endpoints.

## Technology

- Python
- FastAPI
- Uvicorn
- pandas, NumPy, and PyArrow

## Project structure

```text
sensing-engine-backend/
├── app/
│   ├── main.py
│   └── routes/
│       ├── forecast.py
│       ├── health.py
│       └── trends.py
├── data/
│   ├── cleaned/
│   ├── google_signals.csv
│   ├── historic.csv
│   └── social.csv
├── scripts/
│   ├── clean_data.py
│   ├── seed_dummy_data.py
│   ├── smoke_test.py
│   └── smoke_test_forecast.py
├── requirements.txt
└── README.md
```

The API prefers cleaned Parquet files in `data/cleaned/` for historic and social data, falling back to the corresponding CSV files. The scripts include data cleaning, sample data generation, and API smoke checks.

## Local setup

Run these commands from the backend repository root:

```sh
python -m venv .venv
```

Activate the environment:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```sh
# macOS or Linux
source .venv/bin/activate
```

Install dependencies and start the API:

```sh
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

Uvicorn serves locally at `http://127.0.0.1:8000` by default. The app does not read environment variables for its current configuration. CORS is configured in `app/main.py` for local frontend origins on ports 3000, 5173, and 8080.

## API

All API routes are prefixed with `/api`.

| Method | Endpoint | Query parameters |
| --- | --- | --- |
| GET | `/` | — |
| GET | `/api/health` | — |
| GET | `/api/forecast` | Required: `sku`. Optional: `horizon` (7, 14, or 30; default 14), `region` (default `global`), `start_date` (YYYY-MM-DD). |
| GET | `/api/trends` | — |
| GET | `/api/sku-mapping` | — |
| GET | `/api/signals` | — |
| GET | `/api/signals/google` | — |
| GET | `/api/social` | Optional: `hashtag`, `top_n` (default 10). |
| GET | `/api/sources` | — |

The forecast endpoint currently calculates forecasts from a rolling historical mean with weekday multipliers; confidence intervals and stockout risk are heuristic values. It is not a trained forecasting model. The trend and signal endpoints summarize the local datasets.

## Current limitations

- `/api/historic` is not registered, although `scripts/smoke_test.py` includes a request to that path.
- The forecast cache is held in process memory and uses a 24-hour TTL.
- `scripts/smoke_test_forecast.py` imports `requests`, which is not listed in `requirements.txt`.
