# StoreTrack Inventory Management System

StoreTrack is a modern, Ghana-focused inventory and sales management web application built with Python (Flask) and Bootstrap 5.  It is designed for small-to-medium retail stores that need a reliable way to track stock, record sales, and generate actionable reports—all while remaining friendly to mobile devices and automation tools.

---

## ✨ Key Features

* **Product & Stock Management** – Add, edit, and track products with cost/selling prices, safety stock thresholds, and expiry dates.
* **Real-Time Sales** – Shift-aware cashier workflow with automatic stock deductions and audit logging.
* **Alternate Pricing** – Enter an alternate unit price when recording a sale; override/edit the unit price on existing sales. All price overrides are audited.
* **Backdated Sales** – Set a sale date (no future dates) to enter historical sales from notebooks/receipts.
* **Batch Inventory Update (Spreadsheet Upload)** – Drag-and-drop CSV/XLSX to bulk add stock, replace stock, update prices, or perform a full update; robust validation and preview.
* **Admin Settings** – Manager-only page to download full CSV backups (inventory and sales) and perform a full data reset with safeguards and audit log.
* **User Management** – Create users, reset passwords, and manager-only delete (with safeguards against deleting self or users with history).
* **Responsive, Modern UI** – Bootstrap 5 off-canvas sidebar, mobile-friendly tables (horizontal scroll), confirmation modals, toasts, Select2 search, and loading spinners.
* **Audit Trail & Reporting** – Log every critical action; dashboard metrics; inventory valuation; sales summary by day, category, or product; CSV export.
* **Automation-Ready** – Stable `data-testid` attributes, comprehensive automation spec, and sample CSV templates for every batch mode.

---

## 🏗️ Architecture

| Layer                | Tech                                                     |
|----------------------|-----------------------------------------------------------|
| Framework            | Flask 2, Jinja2 templates                                |
| ORM                  | SQLAlchemy + Flask-SQLAlchemy                            |
| Auth                 | Flask-Login, bcrypt                                      |
| Forms & Validation   | Flask-WTF, WTForms                                       |
| Spreadsheet Parsing  | pandas (with optional openpyxl)                          |
| Front-End            | Bootstrap 5, Bootstrap Icons, Select2, jQuery            |
| Misc                 | RapidFuzz (fuzzy product match), Flask-Migrate           |

Folder layout (major parts only):

```
inventory_app/
├─ app.py                # Flask application & routes
├─ models.py             # SQLAlchemy models
├─ batch_inventory_routes.py
├─ templates/
│   ├─ batch_inventory.html
│   ├─ batch_preview.html
│   ├─ sales_summary.html
│   ├─ edit_sale.html
│   └─ settings.html
├─ static/
│   └─ ...               # JS, CSS (theme, mobile), icons
├─ docs/
│   ├─ automation_spec.md
│   └─ samples/          # Sample CSVs for automation
└─ migrations/           # Alembic revision scripts
```

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
flask db upgrade        # apply migrations
flask run               # defaults to http://localhost:5000
```

> **Note**: Environment variables such as `SECRET_KEY`, `DATABASE_URL`, and `FLASK_ENV` can be set in a `.env` file.  See _.env.example_ for a template.

### 2. Admin User

On first run, the app auto-creates a default manager if none exists:

* Username: `admin`
* Password: `changeme123`

You can override these via environment variables before first run:

* `DEFAULT_ADMIN_USER=yourname`
* `DEFAULT_ADMIN_PASS=yourpass`

After login, visit `Users` (manager-only) to create additional users or reset passwords.

### 3. Batch Upload Walk-through

1. Navigate to **Inventory → Batch Inventory** (Manager-only).
2. Download the template for the desired mode (Add-stock, Replace-stock, Update-prices, Full-update).
3. Fill or generate data (see `docs/samples/`).
4. Drag the CSV/XLSX onto the upload box and click **Preview**.
5. Review diffs, fix any validation errors, then click **Confirm Changes**.
6. Success toast appears; inventory is updated and the operation is logged.

Detailed step-by-step selectors and test cases live in `docs/automation_spec.md`.

---

## 🔬 Testing & Automation

| Area          | Tooling / Notes                                        |
|---------------|--------------------------------------------------------|
| Unit / API    | pytest + Flask test client (planned)                   |
| UI Automation | Cypress / Playwright—stable selectors via `data-testid`|
| Sample Files  | `docs/samples/*.csv`                                   |

Run basic lint & unit tests (once tests are in place):

```bash
pytest
```

---

## 🛠️ Deployment

The app runs on any WSGI host. For Render:

1. Set environment variables (`SECRET_KEY`, `DATABASE_URL`, `DEFAULT_ADMIN_*`).
2. Ensure `gunicorn` is in `requirements.txt` and your start command uses it (e.g., `gunicorn app:app`).
3. Configure the service to deploy from the `main` branch. Trigger a deploy.
4. Optional: enable SQLAlchemy pre-ping in your config to avoid stale DB connections on Render.

Migrate automatically on startup or via CI step:

```bash
flask db upgrade
```

---

## 📂 Backup & Recovery

* Daily PostgreSQL dumps (`pg_dump`) recommended.
* Settings → Download offers CSV snapshots of current inventory and sales.

---

## 🌍 Ghana-Specific Considerations

| Aspect      | Implementation                                    |
|-------------|----------------------------------------------------|
| Currency    | Prices stored as floats; UI shows **GH₵** prefix with 2dp|
| Date Format | Forms use ISO `YYYY-MM-DD`; samples/exports may show `DD/MM/YYYY`|
| Mobile Money| Planned integration (MTN MoMo, Vodafone Cash)      |

---

## 🤝 Contributing

PRs are welcome — please follow the conventional commit style and write unit tests for new logic.

```bash
git checkout -b feat/your-feature
git commit -m "feat: add cool thing"
git push --set-upstream origin feat/your-feature
```

---

## 📜 License

This project is licensed under the MIT License.
