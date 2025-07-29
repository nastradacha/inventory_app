# StoreTrack Automation Reference Guide

*Version: 1.0 – generated 2025-07-28*

---

## 1. Purpose & Scope
This document provides a **complete functional map** of the StoreTrack inventory application together with *automation-ready* test cases and selector references.  It is intended for the Automation QA team to create an end-to-end test framework (e.g. Playwright, Cypress, Selenium).

Goals:
1. Describe every feature & workflow in detail.
2. List pre-conditions, steps, and expected results for each test.
3. Provide stable element locators or suggest adding `data-testid` attributes where necessary.
4. Highlight edge-cases and negative scenarios.

---

## 2. Environment Setup
| Item | Details |
|------|---------|
| **URL** | `http://localhost:5000` (default) |
| **Browser Support** | Chromium-based, Firefox, Safari |
| **DB** | SQLite (dev) / PostgreSQL (prod) |
| **Roles** | `admin`, `manager`, `cashier` |
| **Bootstrap Version** | 5.x |
| **Python** | 3.11 |

### 2.1 Seed Admin Account
```bash
flask shell
>>> from app import db, User
>>> User.create_admin('admin', 'password123')
```

---

## 3. Application Architecture (High-Level)

```
app.py          # Flask application factory & routes
models.py       # SQLAlchemy models (User, Product, Sale, Shift, LogEntry …)
forms.py        # WTForms (LoginForm, ProductForm …)
static/
  css/, js/     # Custom styling & behaviour
templates/      # Jinja2 pages – base.html, products.html, users.html …
```

Key integrations:
* **Flask-Login** – auth / session
* **Flask-WTF** – CSRF & forms
* **Bootstrap** – UI components (off-canvas nav, modals, toasts)
* **Select2** – searchable dropdowns
* **RapidFuzz** – fuzzy matching for product search

---

## 4. User Roles & Permissions
| Page/Route | Admin | Manager | Cashier |
|------------|-------|---------|---------|
| Dashboard  | ✅ | ✅ | ✅ |
| Products   | CRUD | CRUD | 🔒 View only |
| Sales      | All  | All  | Create / Void own |
| Batch Upload | ✅ | ✅ | 🔒 |
| Users      | CRUD | 🔒 | 🔒 |
| Reports    | ✅ | ✅ | 🔒 |
| Shifts     | View | View | Open/Close own |

---

## 5. Functional Test Matrix
For each feature below you will find:
* **Functional description**
* **Happy-path test case(s)**
* **Negative / edge test case(s)**
* **Suggested selectors**

> **Selector convention**  
> Wherever possible, pages already contain semantic IDs/classes.  Where a stable hook is missing, add `data-testid="<meaningful-id>"` to the element (example patches are included).

### 5.1 Authentication
| # | Title | Steps | Expected | Selector Hints |
|---|-------|-------|----------|----------------|
| 5.1-A | Login – success | 1. Navigate `/login`  2. Enter valid `admin/password123`  3. Click **Login** | Redirect to `/dashboard`, toast `Login successful` | `#username`, `#password`, `button[type=submit][data-testid=login-btn]` |
| 5.1-B | Login – invalid pwd | As above but wrong pwd | Error toast `Invalid credentials`, stay on `/login` | — |
| 5.1-C | Logout | Click profile dropdown > **Logout** | Redirect to `/login`, session cleared | `a[data-testid=logout]` |

### 5.2 User Management (Admin)
| # | Title | Steps | Expected | Selectors |
|---|-------|-------|----------|-----------|
| 5.2-A | Create cashier | Dashboard > Users > **Add User**  > fill form (`john`, `password`, role `cashier`)  > Save | Success toast, user row appears | `input#username`, `input#password`, `select#role`, `button[data-testid=save-user]` |
| 5.2-B | Reset password | Users list > row `john` > **Reset → changeme123** | Confirmation modal, toast `Password reset` | `button[data-confirm*="Reset password"]` |
| 5.2-C | Validation – duplicate username | Try to add `john` again | Inline validation `Username already exists` | — |

### 5.3 Product Management
| # | Title | Steps | Expected | Selectors |
|---|-------|-------|----------|-----------|
| 5.3-A | Add product | Products > **Add Product** | Product appears in list | `#name`, `#qty_at_hand`, `#cost_price`, `#selling_price` |
| 5.3-B | Edit price change | Products list > **Edit** > change selling price | Price updated; price-change log entry | `button[data-testid=save-product]` |
| 5.3-C | Delete w/ no sales | Add temp product, then delete | Removed, toast `Product deleted` | `button[data-confirm*="Delete"]` |
| 5.3-D | Delete w/ sales | Attempt delete of product with history | Warning toast `Cannot delete` | — |

### 5.4 Inventory – Add Stock / Confirm Add
| # | Title | Steps | Expected | Selectors |
|---|-------|-------|----------|-----------|
| 5.4-A | Increase stock level (with confirm) | 1. Navigate to **Products**  2. Click row product → **Add Stock**  3. Fill Qty `50`, Reference `INV-001`  4. Click **Add**  5. Confirm-Add preview appears (shows pending qty/cost)  6. Click **Confirm Changes** | Success toast `Stock updated!`, product Qty increases by 50, modal closes | `#qty_added`, `#reference`, `button[data-testid=add-stock]`, `#confirmBtn[data-testid=confirm-add?]` |
| 5.4-B | Cancel at confirm screen | Same steps as 5.4-A but click **Cancel** instead of **Confirm Changes** | Info toast `Add-stock cancelled.`, no change in inventory | `button[data-bs-dismiss="modal"]` |
| 5.4-C | Validation – negative qty | Same but enter `-5` | Inline error `Quantity must be positive`, button disabled | — |
| 5.4-D | Spinner & disable | Submit form → button shows spinner & disabled until response | Spinner visible then hidden | — |
| 5.4-B | Validation – negative qty | Same but enter `-5` | Inline error `Quantity must be positive`, button disabled | — |
| 5.4-C | Spinner & disable | Submit form → button shows spinner & disabled until response | Spinner visible then hidden | — |

### 5.5 Record Sale (Cashier)
| # | Title | Steps | Expected | Selectors |
|---|-------|-------|----------|-----------|
| 5.5-A | Record single sale | 1. Dashboard > **Record Sale**  2. Type `Fan` in product Select2 field, pick `Fanta 330ml`  3. Qty `2`, click **Sell** | Toast `Sale recorded`, inventory reduced by 2, sale appears in **Sales Today** | `input.select2-search__field`, `#qty_sold`, `button[data-testid=sell]` |
| 5.5-B | Insufficient stock | Try Qty greater than available | Error toast `Not enough stock` | — |
| 5.5-C | Auto-clear form | After success, fields reset and focus returns to product search | Fields empty | — |
* **Reports & Dashboard widgets**
* **Audit Log**
* **Navigation & Responsive behaviour**

> See `tests_matrix.xlsx` (optional) for an Excel version your team can import into a test-management tool like Xray or Zephyr.

---

## 6. Recommended Element Updates
Below is a **patch list** of places where adding `data-testid` will improve locator stability.  These are low-risk and invisible to end-users.

| Template | Line | Current | Suggested Addition |
|----------|------|---------|--------------------|
| `templates/login.html` | `<button …>` | `<button … data-testid="login-btn">` |
| `templates/products.html` delete button | `<button …>` | `data-testid="delete-product"` |
| `templates/add_stock.html` submit | | `data-testid="add-stock"` |
| `templates/record_sale.html` sell button | | `data-testid="sell"` |
| `templates/users.html` create user | | `data-testid="save-user"` |
| `templates/base.html` logout link | | `data-testid="logout"` |
| `templates/base.html` toast container | | `data-testid="toast-container"` |
| `templates/base.html` sidebar Dashboard link | | `data-testid="nav-dashboard"` |
| `templates/base.html` sidebar Products link | | `data-testid="nav-products"` |
| `templates/batch_preview.html` confirm upload | | `data-testid="apply-batch"` |
| `templates/batch_upload.html` file input | | `data-testid="upload-file"` |
| `templates/batch_upload.html` preview button | | `data-testid="preview-batch"` |
| `templates/batch_upload.html` download template link | | `data-testid="download-template"` |
| `templates/batch_upload.html` download example link | | `data-testid="download-example"` |
| … | … | … | … |

### 5.6 Batch Inventory Upload (Manager)
| # | Title | Steps | Expected | Selectors |
|---|-------|-------|----------|-----------|
| 5.6-A | Upload valid CSV | 1. Sidebar **Batch Upload**  2. Click **Download Template**  3. Fill CSV with 2 new products + 1 update, save  4. Drag or select file in **Upload** page  5. Click **Preview** | Preview table shows 3 rows with correct diff indicators | `input[type=file][data-testid=upload-file]`, `button[data-testid=preview-batch]` |
| 5.6-B | Confirm changes | Continue from 5.6-A, click **Apply Batch** | Success toast `Batch applied!`, inventory updated, audit log entries added | `button[data-testid=apply-batch]` |
| 5.6-C | Cancel preview | From 5.6-A, click **Cancel** | Info toast `Batch cancelled.`, no DB changes | `button[data-bs-dismiss="modal"]` |
| 5.6-D | Upload file with validation errors | Prepare CSV with missing price field, upload & preview | Error table appears with row numbers, **Apply Batch** disabled | `.error-row`, `#errorSummary` |
| 5.6-E | Download template (CSV) | Click **Download Template** | CSV file downloads, correct headers present | `a[data-testid=download-template]` |
| 5.6-F | Download example (CSV) | Click **Download Example** | CSV with sample rows downloads | `a[data-testid=download-example]` |
| 5.6-G | Add-stock mode | Upload `docs/samples/batch_add_stock.csv`, select **Add stock** in Update Mode, preview | Diff shows increased quantities only | — |
| 5.6-H | Replace-stock mode | Upload `docs/samples/batch_replace_stock.csv`, select **Replace stock** | Diff shows new absolute quantities | — |
| 5.6-I | Update prices mode | Upload `docs/samples/batch_update_prices.csv`, select **Update prices** | Diff shows price changes only | — |
| 5.6-J | Full update mode | Upload combined file with qty+prices (create if needed) and select **Full update** | Diff shows quantity, price and meta changes | — |

**Sample CSV templates** (located in `docs/samples/`):

| File | Intended Mode | Description |
|------|---------------|-------------|
| `batch_add_stock.csv` | Add stock | Two existing SKUs with higher quantities. |
| `batch_replace_stock.csv` | Replace stock | Same SKUs but lower quantities to overwrite. |
| `batch_update_prices.csv` | Update prices | Same SKUs, quantity `0`, new cost & selling prices. |
| `batch_full_update.csv` | Full update | Combination of quantity, price and category edits. |

* **Reports & Dashboard widgets**
* **Audit Log**
* **Navigation & Responsive behaviour**

*See separate `automation_selectors.patch` for full diff.*

---

## 7. Example Playwright Test Snippet
```ts
import { test, expect } from '@playwright/test';

test('admin can add product', async ({ page }) => {
  await page.goto('http://localhost:5000/login');
  await page.fill('#username', 'admin');
  await page.fill('#password', 'password123');
  await page.click('[data-testid=login-btn]');

  await page.click('a:has-text("Products")');
  await page.click('text=Add Product');
  await page.fill('#name', 'Fanta 330ml');
  await page.fill('#qty_at_hand', '24');
  await page.fill('#cost_price', '4.00');
  await page.fill('#selling_price', '6.00');
  await page.click('[data-testid=save-product]');

  await expect(page.getByText('Fanta 330ml')).toBeVisible();
});
```

---

## 8. Non-Functional Checks
* **Responsive layout** – viewport 375×812, 1440×900
* **Accessibility** – aria-labels on nav & buttons, contrast ratio
* **Performance** – page load < 2s on dashboard
* **Security** – CSRF token present, session cookies `secure` in prod

---

## 9. Glossary
| Term | Meaning |
|------|---------|
| **SKU** | Stock Keeping Unit |
| **Shift** | Cash session for cashier |
| **Batch Upload** | Spreadsheet-driven bulk inventory update |

---

## 10. Change Log
| Date | Author | Notes |
|------|--------|-------|
| 2025-07-28 | Cascade AI | Initial draft
