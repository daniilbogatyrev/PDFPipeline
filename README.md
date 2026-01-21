# CITY-CAR Funnel Analysis

## Project Description
This project analyses the customer funnel of the CITY-CAR ride‑sharing application. The focus is on: (a) computing warm‑up metrics, (b) deriving funnel KPIs, and (c) producing visual outputs and business insights based on the provided CSV data.

## Project Structure
- [src/main.py](src/main.py): CLI entry point (warm‑up mode, later visualizations)
- [src/funnel_utility.py](src/funnel_utility.py): data loading, validation, transformations, metrics
- [Daten/](Daten): local folder for raw CSV files
- [outputs/](outputs): generated charts/exports

## Data Notice
Due to file size constraints, the raw CSV data files are not tracked in the Git repository. They are provided as part of the project submission and must be placed in the `Daten/` directory.

CSV schema (short):
- app_downloads.csv: app_download_key (PK), platform, download_ts
- signups.csv: user_id (PK), session_id (FK→app_download_key), signup_ts, age_range
- ride_requests.csv: ride_id (PK), user_id, driver_id, request_ts, accept_ts, pickup_ts, dropoff_ts, cancel_ts
- transactions.csv: transaction_id (PK), ride_id (FK), purchase_amount_usd, charge_status, transaction_ts
- reviews.csv: review_id (PK), ride_id (FK), user_id, driver_id, rating, review

## Setup & Reproducibility
- Python 3.11
- Create a virtual environment and install dependencies:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
- Determinism & validation:
	- File paths via `pathlib`
	- Schema checks for required columns
	- Metrics computed with pandas using explicit definitions

## Running the Warm‑up Mode
The warm‑up metrics are printed via a CLI flag:
```bash
python -m src.main --warmup --data-dir Daten
```
If `Daten/` is used as the default location, `--data-dir` can be omitted.

Warm‑up metrics (definitions only):
- App downloads: row count in app_downloads.csv
- Signups: row count in signups.csv
- Ride requests: row count in ride_requests.csv
- Completed rides: `dropoff_ts` not null AND `cancel_ts` is null
- Ride requests and unique users: total rows and distinct `user_id`
- Average duration: `(dropoff_ts - pickup_ts)` in minutes, only completed rides
- Accepted rides: `accept_ts` not null
- Charged rides & revenue: `charge_status == 'Approved'`; sum of `purchase_amount_usd`
- Requests per platform: join app_downloads → signups → ride_requests
- Drop‑off signup → request: share of signups with zero ride requests
