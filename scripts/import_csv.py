"""
Run once:  python scripts/import_csv.py  (inside venv, with DATABASE_URL pointing
to your new Postgres instance on Render)
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import csv
from datetime import datetime


from app import app, db, Product

CSV_PATH =  "my_store_inventory.csv" # Adjust this path as needed


# Mapping from our model fields -> CSV column names
COL = {
    "name":          "Product Name",
    "category":      "Category",
    "expiry_date":   "Expiry",            # format  MM/DD/YYYY  or blank
    "cost_price":    "Cost Price",
    "selling_price": "Selling Price",
    "initial_qty":   "Initial Quantity",
    "qty_at_hand":   "Quantity at Hand",
    # CSV has no safety-stock column; default to 5
}

def parse_date(text):
    if text:
        return datetime.strptime(text, "%m/%d/%Y").date()
    return None        # allow blank


def clean_numeric(val: str) -> str:
    """Remove commas and spaces so '1,234.50' → '1234.50'."""
    return val.replace(",", "").strip()

def float_or_zero(val):
    try:
        return float(clean_numeric(val)) if val else 0.0
    except ValueError:
        return 0.0       # or raise if you’d rather stop on bad data

def int_or_zero(val):
    v = clean_numeric(val)
    return int(float(v)) if v else 0



added, updated = 0, 0


with app.app_context():
    with open(CSV_PATH, newline='', encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row[COL["name"]].strip()
            if not name:
                continue

            p = Product.query.filter_by(name=name).first()
            if p:
                # --- update existing -------------------------------------------------
                p.qty_at_hand   = int_or_zero(row[COL["qty_at_hand"]])
                p.initial_qty   = int_or_zero(row[COL["initial_qty"]])
                p.cost_price    = float_or_zero(row[COL["cost_price"]])
                p.selling_price = float_or_zero(row[COL["selling_price"]])
                p.expiry_date   = parse_date(row[COL["expiry_date"]])
                updated += 1
            else:
                # --- insert new ------------------------------------------------------
                p = Product(
                    name          = name,
                    category      = row.get(COL["category"], "").strip(),
                    expiry_date   = parse_date(row[COL["expiry_date"]]),
                    cost_price    = float_or_zero(row[COL["cost_price"]]),
                    selling_price = float_or_zero(row[COL["selling_price"]]),
                    initial_qty   = int_or_zero(row[COL["initial_qty"]]),
                    qty_at_hand   = int_or_zero(row[COL["qty_at_hand"]]),
                    safety_stock  = 5,                     # default threshold
                )
                db.session.add(p)
                added += 1

        db.session.commit()

print(f"✅  Import finished — {added} added, {updated} updated.")