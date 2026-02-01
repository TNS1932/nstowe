# Portfolio & Market Tools

This project includes:
- FastAPI backend (market data via yfinance and CSV validation)
- Accessible frontend `index.html`
- Upload validation persistence (`validation_reports/`)

## Quick start (local)

1. Create and activate a Python environment.
2. Install dependencies: `python -m pip install -r requirements.txt`
3. Run locally: `python -m uvicorn main:app --reload`

## Deploy to Vercel (suggested)

1. Create a GitHub repo and push this project.
2. Go to https://vercel.com/new and import the GitHub repo.
3. Set the **Project Name** to `nathene` so your site will be `nathene.vercel.app`.
4. During import, Vercel will install `requirements.txt` and deploy the serverless API from `api/`.

Notes:
- The frontend calls API endpoints under `/api/` (e.g. `/api/market/AAPL`, `/api/validate`).
- Validation reports and uploads are stored in `validation_reports/`.

If you want, I can prepare the Git commands to create the repo locally and push, or I can walk you through connecting your GitHub account to Vercel.