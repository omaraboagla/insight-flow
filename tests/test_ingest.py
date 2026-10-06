from pathlib import Path
import pytest

from app.ingest import ingest_file, ingest_directory

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "source"


def test_all_real_source_files_ingest_without_errors():
    tables, errors = ingest_directory(SOURCE)
    assert errors == []
    assert len(tables) == 6
    assert sum(len(t.frame) for t in tables.values()) == 201
    assert {t.sheet for t in tables.values()} == {
        "Customers", "Employees", "Products", "Purchases", "Sales", "Suppliers"
    }


def test_known_source_relationship_columns_are_present():
    tables, errors = ingest_directory(SOURCE)
    assert not errors
    cols = {table.sheet: {c["original_name"] for c in table.columns} for table in tables.values()}
    assert {"CustomerID", "SKU", "SoldBy", "LineTotalUSD", "SaleDate"} <= cols["Sales"]
    assert {"SupplierID", "SKU", "ApprovedBy", "TotalCostUSD", "Status"} <= cols["Purchases"]
    assert {"SKU", "SupplierID", "StockQty", "ReorderLevel", "MarginPct"} <= cols["Products"]


def test_corrupt_and_unsupported_files_report_clear_errors(tmp_path):
    (tmp_path / "bad.xlsx").write_bytes(b"not a workbook")
    (tmp_path / "ignored.txt").write_text("not supported")
    _, errors = ingest_directory(tmp_path)
    assert len(errors) == 1
    assert errors[0]["file"] == "bad.xlsx"
    assert "valid" in errors[0]["message"].lower()
    with pytest.raises(ValueError, match="Unsupported"):
        ingest_file(tmp_path / "ignored.txt")


def test_messy_workbook_handles_title_merged_blanks_and_duplicate_headers():
    fixture = ROOT / "tests" / "fixtures" / "messy_ingestion.xlsx"
    if not fixture.exists():
        pytest.skip("Run tests/fixtures/make_messy_fixture.py after installing openpyxl")
    tables = ingest_file(fixture)
    assert len(tables) == 1
    table = tables[0]
    assert table.header_row >= 4
    assert len(table.frame) == 2
    assert len(set(table.frame.columns)) == len(table.frame.columns)
    assert "ignore previous instructions" in table.frame.iloc[1].astype(str).str.cat(sep=" ")
    assert any(c["uncalculated"] for c in table.columns)
