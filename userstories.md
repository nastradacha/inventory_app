# StoreTrack User Stories Backlog (Prioritized)

This backlog converts our improvement suggestions and roadmap into actionable user stories you can pick up later. Stories are ordered by priority within each section. Each story includes clear acceptance criteria and references to likely files/areas to change.

Legend
- P1: High priority (improves daily operations, reliability, or correctness)
- P2: Medium priority (feature depth, better reporting, operational controls)
- P3: Lower priority / strategic
- P4: Future (after stability)


## P1 — High Priority

### 1) Price override safety (below-cost guard and audit)
As a manager, I want the system to warn if a cashier enters a price below cost, so that we protect margins and avoid mistakes.
- Acceptance Criteria:
  - When recording or editing a sale, if `unit_price < cost_price`, show a red warning: "Below cost".
  - If current user is cashier, require manager confirmation OR block with a clear message (configurable policy).
  - Always write an audit entry indicating who approved/attempted a below-cost sale.
- Notes/Areas: `templates/record_sale.html`, `templates/edit_sale.html`, `app.py (record_sale, edit_sale)`, optional policy flag in config.

### 2) Login hardening and password fields
As an admin, I want secure login UX and brute-force protection, so that user accounts are safeguarded.
- Acceptance Criteria:
  - Replace `StringField` with `PasswordField` in `LoginForm`, `NewUserForm`, `ResetPwdForm`.
  - Add login rate limiting (e.g., 5 attempts/15 minutes per IP/username) with a friendly error.
  - Keep CSRF on forms; no functionality lost.
- Notes/Areas: `forms.py`, `app.py (/login)`, add Flask-Limiter or similar.

### 3) App version footer (deployed commit SHA)
As an operator, I want to see the app version on every page, so I can verify production is running the latest build.
- Acceptance Criteria:
  - Footer shows short git SHA (e.g., `d9b1fdd`) and environment (e.g., Production).
  - Hidden on small screens or collapsible.
- Notes/Areas: `templates/base.html` (inject value via context processor/env var).

### 4) Sales Summary filters UX: date presets + sticky filters
As a manager, I want quick presets and persistent filters, so I can analyze faster without re-entering dates.
- Acceptance Criteria:
  - Presets: Today, Yesterday, This Week, MTD, Last 30 Days.
  - Switching breakdown (Summary/Category/Product) preserves current dates and selected filters without re-downloading CSV.
  - CSV and XLSX export buttons both available.
- Notes/Areas: `templates/sales_summary.html`, `app.py (sales_summary)`, add XLSX via pandas/openpyxl.

### 5) Sales list: filters and pagination
As a manager, I want to filter the sales list by product/date/cashier and paginate results, so that I can find records quickly.
- Acceptance Criteria:
  - Filters: date range, product (search-as-you-type), cashier.
  - Pagination (20-50 per page) with total count.
- Notes/Areas: `@app.route('/sales')`, `templates/sales.html`.

### 6) Prevent deleting the last manager
As an admin, I want to avoid lockouts by ensuring at least one manager remains.
- Acceptance Criteria:
  - Attempting to delete the last manager shows a warning toast and blocks the action.
  - Still allow deleting a manager if another manager user remains.
- Notes/Areas: `app.py (delete_user)`, `models.py (User)`.

### 7) User self-service password change
As a user, I want to change my own password, so that I don’t need an admin for routine changes.
- Acceptance Criteria:
  - New page "Change Password" accessible from the header dropdown.
  - Requires current password and a new password entry (with confirmation).
  - Success toast and forced re-login optional.
- Notes/Areas: new route + template, `forms.py` new form, `app.py` new handler.


## P2 — Medium Priority

### 8) Monetary precision migration (Decimal/Numeric)
As an owner, I want accurate money math, so that totals and reports do not have rounding errors.
- Acceptance Criteria:
  - Migrate all price/money fields to `Numeric(12,2)` in the DB and `Decimal` handling in Python.
  - Update all arithmetic to use Decimal and format with 2dp in UI.
  - Create Alembic migration, data backfilled correctly, zero downtime planar (or maintenance window).
- Notes/Areas: `models.py` (Product.cost_price/selling_price, Sale.unit_price), migrations, all revenue calculations.

### 9) DB performance and reliability (Render)
As an operator, I want stable DB connections and fast queries, so that the app is reliable under load.
- Acceptance Criteria:
  - Enable SQLAlchemy `pool_pre_ping=True` and set reasonable `pool_recycle`.
  - Add indexes on `Sale.date`, `Sale.product_id`, `LogEntry.timestamp`.
  - Verify improved performance (profiling basic endpoints).
- Notes/Areas: DB config, migrations for indexes.

### 10) Sales returns/exchanges (partial return)
As a manager, I want to handle partial returns/exchanges with proper stock adjustments and audit, so that customer issues are resolved correctly.
- Acceptance Criteria:
  - Return flow puts quantity back to stock and logs audit.
  - Revenue impact recorded correctly (negative sale or adjustment entry).
  - Prevent abuse: require manager permission for returns beyond X days.
- Notes/Areas: new routes/forms/templates, `models.py` may need a returns table or negative sales convention.

### 11) Inventory adjustments module (stocktake & reasons)
As an inventory clerk, I want to adjust stock with reasons (spoilage, shrink, count), so that inventory remains accurate and auditable.
- Acceptance Criteria:
  - Adjust stock for a product with reason codes; write an inventory movement log.
  - Show adjustment history in product detail.
- Notes/Areas: new model `InventoryMovement`, new routes/templates, `products.html` links.

### 12) Batch upload safety and scale
As a manager, I want clearer error handling and scalability for large sheets.
- Acceptance Criteria:
  - Download a CSV of failed rows with error messages.
  - Optional: queue processing for very large files and show progress (RQ/Celery).
- Notes/Areas: `batch_inventory_routes.py`, preview/confirm steps, background worker later.


## P3 — Lower Priority / Strategic

### 13) VAT and tax handling
As an owner, I want to record VAT, so that my reports and invoices reflect tax rules.
- Acceptance Criteria:
  - Configure VAT percentage; compute on sales lines.
  - Show VAT breakdown in reports and (future) invoices/receipts.
- Notes/Areas: models, `sales_summary`, UI labels, configuration.

### 14) Supplier & purchase orders
As a store manager, I want to record suppliers and purchase/receiving orders, so that COGS and stock provenance are tracked.
- Acceptance Criteria:
  - Supplier table; purchase order + lines; receiving updates stock and cost price.
  - Reports reflect COGS more accurately.
- Notes/Areas: new models and routes, significant UI.

### 15) Mobile Money (MoMo) integration (exploratory)
As an owner, I want to accept payments via MTN MoMo/Vodafone Cash, so that customers have more options.
- Acceptance Criteria:
  - Research APIs; add config placeholders and mock flow in test mode.
  - Collect transaction reference in sales record (optional).
- Notes/Areas: integrations and security considerations.

### 16) Offline capability (lightweight)
As a cashier, I want a basic offline fallback if internet drops, so that I can keep recording and sync later.
- Acceptance Criteria:
  - Minimal PWA cache shell; queue sales locally and sync when online.
  - Clear warnings when offline/unsynced.
- Notes/Areas: PWA, sync endpoints, data integrity.


## P4 — Future (after stability)

### 17) Multi-store support
As a regional manager, I want to manage multiple stores and see combined reports, so that I can run a chain efficiently.
- Acceptance Criteria:
  - Store entity; user-to-store mapping; per-store inventory/sales; centralized reporting.
  - Role-based access across stores.
- Notes/Areas: new models, scoping, deployment planning.


## Cross-Cutting: QA & Observability

### 18) Automated tests for critical flows
As a developer, I want tests for key scenarios, so that regressions are caught before production.
- Acceptance Criteria:
  - Tests for login success/failure, record sale (with/without override), edit sale price (audit), backdated sale, CSV exports, batch preview/confirm.
  - GitHub Actions CI running flake8/black/pytest.
- Notes/Areas: `tests/`, CI workflow.

### 19) Structured logging + error notifications
As an operator, I want structured logs and alerts on errors, so that I can respond quickly.
- Acceptance Criteria:
  - JSON logs with request id, user, route, latency; 400/500 error capture.
  - Optional Slack/email webhook for critical errors.
- Notes/Areas: logging config + small wrappers.


## Ghana-Specific Enhancements

### 20) Cedi formatting & date format consistency
As a cashier/manager in Ghana, I want consistent GH₵ formatting and dates, so the app matches local expectations.
- Acceptance Criteria:
  - Display GH₵ with thousands separators and 2dp everywhere.
  - Dates default to `DD/MM/YYYY` in human-facing reports; forms remain `YYYY-MM-DD`.
- Notes/Areas: Jinja filters/utilities, templates.


---

## Getting Started Suggestion (Sprint 1)
- Implement stories 1, 2, 3, and 4 (price override safety, login hardening, app version footer, sales summary presets + sticky filters).
- Add basic tests for these flows.

## References
- Current code areas: `app.py`, `models.py`, `forms.py`, `templates/*`, `batch_inventory_routes.py`.
- Recently implemented: alternate price (new sale + edit), backdated sale, CSV auto-download fix in reports, user delete & trims, settings reset.
