import logging
import yfinance as yf
import pandas as pd
import os
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI()
logger = logging.getLogger("portfolio_app")


def sanitize_portfolio(df: pd.DataFrame) -> pd.DataFrame:
    """Return a sanitized copy of the portfolio DataFrame.

    Rules:
    - Drop rows with missing or empty symbol
    - Convert 'shares' and 'price' to numeric; coerce errors to NaN
    - Keep only rows with shares > 0
    """
    df = df.copy()
    if "symbol" not in df.columns:
        return pd.DataFrame(columns=["symbol", "shares", "price"])

    df = df.dropna(subset=["symbol"])  # symbol required
    df["symbol"] = df["symbol"].astype(str).str.strip()

    df["shares"] = pd.to_numeric(df.get("shares", 0), errors="coerce")
    df["price"] = pd.to_numeric(df.get("price", 0), errors="coerce")

    # Keep only rows with valid shares > 0 and numeric price (non-NaN)
    df = df[df["shares"].notna() & (df["shares"] > 0) & df["price"].notna()]
    return df


def load_and_sanitize_portfolio(path: str = "portfolio.csv") -> pd.DataFrame:
    try:
        df = pd.read_csv(path)
    except FileNotFoundError:
        return pd.DataFrame(columns=["symbol", "shares", "price"])
    except Exception as e:
        logger.exception("Failed to read portfolio file: %s", e)
        return pd.DataFrame(columns=["symbol", "shares", "price"])

    return sanitize_portfolio(df)


# Serve static assets and index
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", include_in_schema=False)
def root():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    raise HTTPException(status_code=404, detail="index not found")


# ---------- MARKET ENGINE ----------
@app.get("/market/{symbol}")
def market_data(symbol: str):
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="5y")
    except Exception as e:
        logger.exception("yfinance error for %s: %s", symbol, e)
        raise HTTPException(status_code=503, detail=f"market data unavailable for {symbol}")

    if hist is None or hist.empty:
        return []

    return hist.reset_index().to_dict(orient="records")


# ---------- PORTFOLIO ENGINE ----------
@app.get("/portfolio/{symbol}")
def portfolio_data(symbol: str):
    portfolio = load_and_sanitize_portfolio()
    trades = portfolio[portfolio["symbol"] == symbol]

    total_shares = int(trades["shares"].sum()) if not trades.empty else 0
    if total_shares == 0:
        return {"symbol": symbol, "total_shares": 0, "message": "no shares in portfolio"}

    avg_cost = (trades["shares"] * trades["price"]).sum() / total_shares

    try:
        stock = yf.Ticker(symbol)
        price_series = stock.history(period="1d")["Close"]
    except Exception as e:
        logger.exception("yfinance error for %s: %s", symbol, e)
        raise HTTPException(status_code=503, detail=f"market data unavailable for {symbol}")

    if price_series.empty:
        return {"symbol": symbol, "message": "no price data available"}

    price = float(price_series.iloc[-1])

    equity = total_shares * price
    pnl = (price - avg_cost) * total_shares
    roi = (price - avg_cost) / avg_cost * 100 if avg_cost != 0 else None

    return {
        "symbol": symbol,
        "total_shares": total_shares,
        "avg_cost": round(avg_cost, 2),
        "current_price": round(price, 2),
        "equity": round(equity, 2),
        "pnl": round(pnl, 2),
        "roi_percent": round(roi, 2) if roi is not None else None
    }


@app.post("/validate")
async def validate_csv(file: UploadFile = File(...)):
    """Validate a CSV upload and return a report about invalid rows and a sanitized sample."""
    try:
        content = await file.read()
        text = content.decode("utf-8", errors="replace")
        from io import StringIO
        df = pd.read_csv(StringIO(text))
    except Exception as e:
        logger.exception("Failed to parse uploaded CSV: %s", e)
        raise HTTPException(status_code=400, detail="invalid CSV file")

    original_rows = len(df)
    sanitized = sanitize_portfolio(df)
    sanitized_rows = len(sanitized)
    dropped_rows = original_rows - sanitized_rows

    issues = []
    for idx, row in df.iterrows():
        row_issues = []
        raw_symbol = row.get("symbol")
        symbol = None if pd.isna(raw_symbol) else str(raw_symbol).strip()
        if symbol is None or symbol == "":
            row_issues.append("missing symbol")
        shares = pd.to_numeric(row.get("shares"), errors="coerce")
        if pd.isna(shares) or shares <= 0:
            row_issues.append("invalid shares")
        price = pd.to_numeric(row.get("price"), errors="coerce")
        if pd.isna(price):
            row_issues.append("invalid price")
        if row_issues:
            issues.append({"row_index": int(idx), "symbol": symbol, "issues": row_issues})

    # Make sanitized sample JSON-safe by replacing NaN with None
    def _json_safe(o):
        import math
        if isinstance(o, dict):
            return {k: _json_safe(v) for k, v in o.items()}
        if isinstance(o, list):
            return [_json_safe(i) for i in o]
        if isinstance(o, float) and math.isnan(o):
            return None
        return o

    sanitized_sample = _json_safe(sanitized.head(5).to_dict(orient="records"))

    # Persist upload and report
    os.makedirs("validation_reports/uploads", exist_ok=True)
    os.makedirs("validation_reports/reports", exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    upload_path = f"validation_reports/uploads/{ts}_{file.filename}"
    with open(upload_path, "wb") as f:
        f.write(content)

    report = {
        "timestamp": ts,
        "filename": file.filename,
        "original_rows": original_rows,
        "sanitized_rows": sanitized_rows,
        "dropped_rows": dropped_rows,
        "issues": issues,
        "sanitized_sample": sanitized_sample,
    }
    report_path = f"validation_reports/reports/{ts}_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return report
