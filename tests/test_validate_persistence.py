import os
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_validate_persistence(tmp_path):
    # Post a small valid CSV and ensure report and upload are persisted
    csv = "symbol,shares,price\nAAPL,10,150\n"
    files = {"file": ("upload.csv", csv, "text/csv")}
    r = client.post("/validate", files=files)
    assert r.status_code == 200
    j = r.json()
    # Check that report file exists
    reports_dir = os.path.join("validation_reports", "reports")
    uploads_dir = os.path.join("validation_reports", "uploads")
    assert os.path.isdir(reports_dir)
    assert os.path.isdir(uploads_dir)
    # at least one file in each
    assert any(os.scandir(reports_dir))
    assert any(os.scandir(uploads_dir))
