import pandas as pd
import pytest
from fastapi.testclient import TestClient

import main
from main import app

client = TestClient(app)


def test_sanitize_portfolio():
    df = pd.DataFrame({
        "symbol": ["A", None, "B", "C", "D"],
        "shares": [10, 5, "NaN", 0, "2"],
        "price": [100, 200, 300, "NaN", 5]
    })

    out = main.sanitize_portfolio(df)
    # Should drop row with None symbol, drop non-positive shares, coerce strings
    assert "A" in out["symbol"].values
    assert "D" in out["symbol"].values
    assert "B" not in out["symbol"].values
    assert out.shape[0] == 2


def test_portfolio_endpoint_no_shares(monkeypatch):
    monkeypatch.setattr(main, "load_and_sanitize_portfolio", lambda: pd.DataFrame(columns=["symbol", "shares", "price"]))
    r = client.get("/portfolio/FOO")
    assert r.status_code == 200
    assert r.json()["total_shares"] == 0


class FakeTicker:
    def __init__(self, symbol):
        self.symbol = symbol

    def history(self, period="1d"):
        if period == "1d":
            # return a DataFrame with Close
            return pd.DataFrame({"Close": [7.0]})
        return pd.DataFrame({"Close": [1.0]})


def test_portfolio_endpoint_valid(monkeypatch):
    df = pd.DataFrame({"symbol": ["FOO"], "shares": [10], "price": [5]})
    monkeypatch.setattr(main, "load_and_sanitize_portfolio", lambda: df)
    monkeypatch.setattr(main.yf, "Ticker", FakeTicker)

    r = client.get("/portfolio/FOO")
    assert r.status_code == 200
    j = r.json()
    assert j["symbol"] == "FOO"
    assert j["total_shares"] == 10
    assert j["current_price"] == 7.0
    # equity = 10 * 7 = 70
    assert j["equity"] == 70


def test_market_endpoint_empty(monkeypatch):
    class EmptyTicker:
        def __init__(self, symbol):
            pass

        def history(self, period="5y"):
            return pd.DataFrame()

    monkeypatch.setattr(main.yf, "Ticker", EmptyTicker)
    r = client.get("/market/XYZ")
    assert r.status_code == 200
    assert r.json() == []


def test_validate_endpoint_good():
    csv = "symbol,shares,price\nAAPL,10,150\nJNJ,5,140\n"
    files = {"file": ("good.csv", csv, "text/csv")}
    r = client.post("/validate", files=files)
    assert r.status_code == 200
    j = r.json()
    assert j["original_rows"] == 2
    assert j["sanitized_rows"] == 2


def test_validate_endpoint_bad():
    csv = "symbol,shares,price\n,5,100\nBAD,notnum,10\nBADPRICE,2,foo\n"
    files = {"file": ("bad.csv", csv, "text/csv")}
    r = client.post("/validate", files=files)
    assert r.status_code == 200
    j = r.json()
    assert j["original_rows"] == 3
    assert j["sanitized_rows"] == 0
    assert j["dropped_rows"] == 3
    assert len(j["issues"]) == 3
