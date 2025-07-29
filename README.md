# StoreTrack Inventory Management System

StoreTrack is a modern, Ghana-focused inventory and sales management web application built with Python (Flask) and Bootstrap 5.  It is designed for small-to-medium retail stores that need a reliable way to track stock, record sales, and generate actionable reports—all while remaining friendly to mobile devices and automation tools.

---

## ✨ Key Features

* **Product & Stock Management** – Add, edit, and track products with cost / selling prices, safety stock thresholds, and expiry dates.
* **Real-Time Sales Recording** – Shift-aware cashier workflow with automatic stock deductions and audit logging.
* **Batch Inventory Update (Spreadsheet Upload)** – Drag-and-drop CSV or XLSX files to bulk add stock, replace stock, update prices, or perform a full update.
* **Role-Based Access Control** – Manager vs. Cashier routes, with CSRF protection and secure password hashing (bcrypt).
* **Responsive UI** – Bootstrap 5 off-canvas sidebar, mobile-first tables, confirmation modals, toasts, and loading spinners.
* **Audit Trail & Reporting** – Log every critical action, view dashboard metrics, and download templates for offline analysis.
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
| Front-End            | Bootstrap 5, FontAwesome, Select2, vanilla JS            |
| Misc                 | RapidFuzz (fuzzy product match), Flask-Migrate           |

Folder layout (major parts only):

```
inventory_app/
├─ app.py                # Application factory + blueprint registration
├─ models.py             # SQLAlchemy models
├─ batch_inventory_routes.py
├─ templates/
│   ├─ batch_inventory.html
│   └─ batch_preview.html
├─ static/
│   └─ ...               # JS, CSS, icons
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

### 2. Create an Admin User

Run the interactive shell:

```bash
flask shell
>>> from app import db, create_app
>>> from models import User
>>> u = User(username='admin', role='manager')
>>> u.set_password('changeme')
>>> db.session.add(u); db.session.commit()
```

Login as *admin / changeme* and immediately change the password.

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

The app runs on any WSGI host; for Render or Heroku:

1. Set environment variables (see Quick Start).
2. Ensure `gunicorn` is in `requirements.txt`.
3. `render.yaml` / `Procfile` already included (if applicable).

Migrate automatically on startup or via CI step:

```bash
flask db upgrade
```

---

## 📂 Backup & Recovery

* Daily PostgreSQL dumps (`pg_dump`) recommended.
* `backup/` folder can store downloaded CSV snapshots of current inventory.

---

## 🌍 Ghana-Specific Considerations

| Aspect      | Implementation                                    |
|-------------|----------------------------------------------------|
| Currency    | Prices stored as `Decimal`; UI shows **GH₵** prefix|
| Date Format | DD/MM/YYYY in templates and sample files           |
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
