from flask import Flask, render_template, redirect, url_for, flash, request, abort, session,send_file, make_response, jsonify
from flask_login import LoginManager, login_user, login_required, current_user, logout_user
from flask_wtf import CSRFProtect 
from functools import wraps
import bcrypt, os
import uuid, traceback
from forms import LoginForm 

from datetime import date, datetime,timedelta
from config import Config
from models import db, Product, Sale, User, PriceChange, LogEntry, Shift
from forms import AddStockForm, RecordSaleForm, NewUserForm, ResetPwdForm, EditProductForm, EditSaleForm, BatchInventoryForm
from rapidfuzz import fuzz
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import subprocess

from sqlalchemy import func, cast, Date, inspect, text
from sqlalchemy.exc import SQLAlchemyError
import pandas as pd
from io import StringIO
from io import BytesIO
from flask_migrate import Migrate
from batch_inventory_routes import batch_inventory_bp

# import weasyprint


app = Flask(__name__)
app.config.from_object(Config)

# Enable CSRF protection for every POST form
csrf = CSRFProtect(app)

# Rate limiting (Story 2): keep defaults off app-wide; limit only the login route
limiter = Limiter(key_func=get_remote_address, default_limits=[])
limiter.init_app(app)

# Register blueprints
app.register_blueprint(batch_inventory_bp)

db.init_app(app)
migrate = Migrate(app, db)

def log(action, details):
    db.session.add(
        LogEntry(user=current_user.username,
                 action=action,
                 details=details))
    db.session.commit()

# --- database setup -------------------------------------------------------
# Flask 3.0 removed the before_first_request decorator. We now create the
# tables once at startup, inside an application context.
with app.app_context():
    db.create_all()



    # --- one-time bootstrap ------------------------------------------------
    if not User.query.filter_by(role='manager').first():
        default_user = os.getenv('DEFAULT_ADMIN_USER', 'admin')
        default_pass = os.getenv('DEFAULT_ADMIN_PASS', 'changeme123')

        User.create(default_user, default_pass, 'manager')
        app.logger.warning(
            f'*** Created default manager '
            f'username={default_user} password={default_pass} ***'
        )
    # ----------------------------------------------------------------------

@app.route('/')
@login_required
def dashboard():
    currency = app.config['CURRENCY_SYMBOL']
    # Safe defaults
    products = []
    total_cost = 0.0
    total_value = 0.0
    total_profit = 0.0
    today_rev = 0.0
    today_units = 0
    my_today_rev = 0.0
    my_today_units = 0
    low_stock = []
    top_sales = []

    # 1) Products and valuation
    try:
        products = Product.query.all()
        total_cost = sum(p.qty_at_hand * p.cost_price for p in products)
        total_value = sum(p.qty_at_hand * p.selling_price for p in products)
        total_profit = total_value - total_cost
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass

    # 2) Store totals today
    today = date.today()
    try:
        today_row = (
            db.session.query(
                db.func.coalesce(
                    db.func.sum(
                        Sale.qty_sold * db.func.coalesce(Sale.unit_price, Product.selling_price)
                    ),
                    0.0,
                ).label('rev'),
                db.func.coalesce(db.func.sum(Sale.qty_sold), 0).label('units'),
            )
            .join(Product)
            .filter(Sale.date == today)
            .first()
        )
        today_rev = float(today_row[0] or 0.0)
        today_units = int(today_row[1] or 0)
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass

    # 3) Cashier personal totals today (only if column exists)
    if current_user.is_authenticated and current_user.role == 'cashier':
        has_cashier_col = False
        try:
            cols = [c['name'] for c in inspect(db.engine).get_columns('sale')]
            has_cashier_col = 'cashier_id' in cols
        except Exception:
            has_cashier_col = False
        if has_cashier_col:
            try:
                my_row = (
                    db.session.query(
                        db.func.coalesce(
                            db.func.sum(
                                Sale.qty_sold * db.func.coalesce(Sale.unit_price, Product.selling_price)
                            ),
                            0.0,
                        ).label('rev'),
                        db.func.coalesce(db.func.sum(Sale.qty_sold), 0).label('units'),
                    )
                    .join(Product)
                    .filter(Sale.date == today)
                    .filter(Sale.cashier_id == current_user.id)
                    .first()
                )
                my_today_rev = float((my_row[0] or 0.0))
                my_today_units = int((my_row[1] or 0))
            except Exception:
                try:
                    db.session.rollback()
                except Exception:
                    pass

    # 4) Low stock list
    try:
        low_stock = (
            Product.query
            .filter(Product.qty_at_hand < Product.safety_stock)
            .order_by(Product.qty_at_hand.asc())
            .limit(20)
            .all()
        )
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass

    # 5) Top sellers
    try:
        top_sales = (
            db.session.query(Product.name, db.func.sum(Sale.qty_sold).label('units'))
            .join(Sale)
            .group_by(Product.name)
            .order_by(db.desc('units'))
            .limit(5)
            .all()
        )
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass

    return render_template('dashboard.html', **locals())


@app.route('/ping')
@login_required
def ping():
    # keepalive endpoint to prevent session timeouts during rapid entry
    return ('', 204)

@app.route('/favicon.ico')
def favicon_redirect():
    # serve svg favicon when browser requests .ico path
    return redirect(url_for('static', filename='favicon.svg'))

@app.route('/healthz')
def healthz():
    # Health check for Render. Try a lightweight DB ping but return ok even if DB fails,
    # so the service can come up and migrations can run during preDeploy.
    try:
        db.session.execute(text('SELECT 1'))
        return 'ok', 200
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        return 'ok', 200

@app.route('/add-stock', methods=['GET', 'POST'])
def add_stock():
    form = AddStockForm()

    # 2️⃣  ***GET branch*** — needed for the Select2 dropdown
    if request.method == 'GET':                         # ← add this block
        all_names = [p.name for p in Product.query.order_by(Product.name)]
        return render_template('add_stock.html', form=form, all_names=all_names)

    # 3️⃣  POST branch (your current code) -------------------------------
    if form.validate_on_submit():
        similar = None
        for prod in Product.query.all():
            score = fuzz.token_set_ratio(form.name.data.lower(), prod.name.lower())
            if score > 85:
                similar = prod.name
                break

        if similar:
            clean_data = form.data.copy()
            if clean_data['expiry_date']:  
                clean_data['expiry_date'] = clean_data['expiry_date'].isoformat()  # Convert to string
            session['pending_product'] = clean_data  # Stash cleaned form data

            flash(
                f'Product “{similar}” looks similar. '
                'Click Confirm to restock it or Cancel to go back.',
                'warning'
            )
            return redirect(url_for('confirm_add'))

        # → no similar found or user confirmed duplication
        p = Product.query.filter_by(name=form.name.data).first()
        if p:  # restock existing
            p.qty_at_hand += form.quantity.data
            p.initial_qty += form.quantity.data
            p.cost_price = form.cost_price.data
            p.selling_price = form.selling_price.data
            p.expiry_date = form.expiry_date.data
            p.safety_stock = form.safety_stock.data
        else:  # new product
            p = Product(
                name=form.name.data,
                category=form.category.data,
                expiry_date=form.expiry_date.data,
                cost_price=form.cost_price.data,
                selling_price=form.selling_price.data,
                initial_qty=form.quantity.data,
                qty_at_hand=form.quantity.data,
                safety_stock=form.safety_stock.data
            )
            db.session.add(p)
        db.session.commit()
        flash('Stock updated!', 'success')
        return redirect(url_for('dashboard'))

    # This return only runs if form fails validation
    return render_template('add_stock.html', form=form, all_names=[])


@app.route('/search-products')
@login_required
def search_products():
    search_term = request.args.get('q', '').lower()
    in_stock = request.args.get('in_stock', 'true') == 'true'
    
    # Base query
    query = Product.query
    
    # Filter in-stock items if requested
    if in_stock:
        query = query.filter(Product.qty_at_hand > 0)
    
    # Search by name or category
    if search_term:
        query = query.filter(
            (func.lower(Product.name).contains(search_term)) | 
            (func.lower(Product.category).contains(search_term)))
    
    # Limit results and format for Select2
    products = query.order_by(Product.name).limit(20).all()
    
    results = [{
        'id': p.id,
        'text': f"{p.name} ({p.category}) - Stock: {p.qty_at_hand}",
        'stock': p.qty_at_hand
    } for p in products]
    
    return jsonify({'items': results})




@app.route('/product-stock/<int:pid>')
@login_required
def product_stock(pid):
    """Return current stock, list price, and cost for a single product.
    Used by Record Sale UI for hints and below-cost warnings (Story 1).
    """
    p = Product.query.get(pid)
    if not p:
        return jsonify(success=False, error='not_found'), 404
    return jsonify(success=True,
                   stock=p.qty_at_hand,
                   price=float(p.selling_price or 0.0),
                   cost=float(p.cost_price or 0.0))

@app.route('/record-sale', methods=['GET', 'POST'])
@login_required
def record_sale():
    form = RecordSaleForm()
    
    # Remove the choices population completely
    # Preserve selected sale_date from query string for quick multi-entry
    if request.method == 'GET':
        qs_date = request.args.get('date')
        if qs_date:
            try:
                form.sale_date.data = date.fromisoformat(qs_date)
            except ValueError:
                pass

    if form.validate_on_submit():
        # Get product from ID instead of form choices
        product = Product.query.get(form.product_id.data)
        
        if not product:
            flash('Product not found!', 'danger')
            # keep the chosen date when returning to the form
            return redirect(url_for('record_sale', date=form.sale_date.data.isoformat() if form.sale_date.data else None))
            
        if product.qty_at_hand < form.quantity.data:
            flash('Not enough stock!', 'danger')
        else:
            # Below-cost guard (Story 1)
            alt_price = form.unit_price.data
            effective = float(alt_price) if alt_price else float(product.selling_price or 0)
            if effective < float(product.cost_price or 0):
                if current_user.role != 'manager':
                    # Block for cashiers; audit attempt
                    db.session.add(LogEntry(
                        user=current_user.username,
                        action='below_cost_attempt_blocked',
                        details=f"Attempted {form.quantity.data} × {product.name} at {app.config['CURRENCY_SYMBOL']}{effective:.2f} (< cost {app.config['CURRENCY_SYMBOL']}{product.cost_price:.2f})"
                    ))
                    db.session.commit()
                    flash('Price below cost is not allowed. Please ask a manager.', 'danger')
                    return redirect(url_for('record_sale', date=form.sale_date.data.isoformat() if form.sale_date.data else None))
                else:
                    # Allow for managers but audit override
                    db.session.add(LogEntry(
                        user=current_user.username,
                        action='below_cost_override',
                        details=f"Manager approved {form.quantity.data} × {product.name} at {app.config['CURRENCY_SYMBOL']}{effective:.2f} (< cost {app.config['CURRENCY_SYMBOL']}{product.cost_price:.2f})"
                    ))

            # Proceed to record sale
            product.qty_at_hand -= form.quantity.data
            sale = Sale(
                product_id=product.id,
                qty_sold=form.quantity.data,
                date=form.sale_date.data,
                unit_price=alt_price if alt_price else None,
            )
            # Set cashier only if DB has the column (handles rolling migrations safely)
            try:
                cols = [c['name'] for c in inspect(db.engine).get_columns('sale')]
                if 'cashier_id' in cols:
                    sale.cashier_id = current_user.id
            except Exception:
                pass
            db.session.add(sale)

            # Audit if an alternate price was used
            if alt_price and float(alt_price) != float(product.selling_price or 0):
                db.session.add(LogEntry(
                    user=current_user.username,
                    action='sale_alt_price',
                    details=f"{form.quantity.data} × {product.name} at {app.config['CURRENCY_SYMBOL']}{alt_price:.2f} (list {app.config['CURRENCY_SYMBOL']}{product.selling_price:.2f})"
                ))

            db.session.commit()
            if alt_price:
                flash('Sale recorded with alternate price.', 'success')
            else:
                flash('Sale recorded.', 'success')
            # Redirect back to Record Sale to allow rapid multi-entry; preserve date
            return redirect(url_for('record_sale', date=form.sale_date.data.isoformat() if form.sale_date.data else None))
    
    return render_template('record_sale.html', form=form, currency=app.config['CURRENCY_SYMBOL'], today=date.today().isoformat())


login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def manager_required(f):
    @wraps(f)
    @login_required
    def wrapper(*args, **kwargs):
        if current_user.role != 'manager':
            abort(403)
        return f(*args, **kwargs)
    return wrapper


def _ip_limit_decorator():
    """Return a pass-through decorator in Production to disable IP limit,
    otherwise apply the configured per-IP limiter in non-production.
    """
    env = (app.config.get('APP_ENV') or os.getenv('APP_ENV') or 'Development').lower()
    if env == 'production':
        def passthrough(fn):
            return fn
        return passthrough
    else:
        return limiter.limit(
            lambda: app.config.get('LOGIN_IP_LIMIT', '200 per 15 minutes'),
            methods=["POST"],
            key_func=get_remote_address
        )

@app.route('/login', methods=['GET', 'POST'])
@csrf.exempt                              # allow login even if token missing (fallback)
@limiter.limit(lambda: app.config.get('LOGIN_RATE_LIMIT', '50 per 15 minutes'), methods=["POST"], key_func=lambda: (request.form.get("username") or get_remote_address()))
@_ip_limit_decorator()
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = (form.username.data or '').strip()
        password = (form.password.data or '').strip()
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.checkpw(password.encode(), user.pw_hash.encode()):
            login_user(user)
            # keep session alive through the workday
            session.permanent = True
            return redirect(url_for('dashboard'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html', form=form)



@app.route('/confirm-add', methods=['GET', 'POST'])
@login_required
def confirm_add():
    pending = session.get('pending_product')
    if not pending:
        return redirect(url_for('add_stock'))

    if request.method == 'POST':
        if 'confirm' in request.form:
            # rebuild form object from stored data
            form_data = pending
            # Either treat as restock or create new product (same logic you already have)
            # ensure expiry_date is a Python date object
            expiry_val = None
            if form_data.get('expiry_date'):
                expiry_raw = form_data['expiry_date']
                if isinstance(expiry_raw, str) and expiry_raw:
                    try:
                        expiry_val = date.fromisoformat(expiry_raw)
                    except ValueError:
                        # fallback: try dd/mm/YYYY format
                        try:
                            expiry_val = datetime.strptime(expiry_raw, '%d/%m/%Y').date()
                        except ValueError:
                            expiry_val = None
                elif isinstance(expiry_raw, date):
                    expiry_val = expiry_raw

            p = Product.query.filter_by(name=form_data['name']).first()
            if p:
                p.qty_at_hand += int(form_data['quantity'])
                p.initial_qty += int(form_data['quantity'])
                if expiry_val:
                    p.expiry_date = expiry_val
            else:
                p = Product(
                    name=form_data['name'],
                    category=form_data['category'],
                    expiry_date=expiry_val,
                    cost_price=float(form_data['cost_price']),
                    selling_price=float(form_data['selling_price']),
                    initial_qty=int(form_data['quantity']),
                    qty_at_hand=int(form_data['quantity']),
                )
                db.session.add(p)

            db.session.commit()
            flash('Stock updated!', 'success')
        else:
            flash('Add-stock cancelled.', 'info')

        session.pop('pending_product', None)
        return redirect(url_for('add_stock'))

    # GET request: show confirmation page
    return render_template('confirm_add.html', pending=pending)

@app.route('/users', methods=['GET', 'POST'])
@login_required
@manager_required
def users():
    form = NewUserForm()
    if form.validate_on_submit():
        username = (form.username.data or '').strip()
        password = (form.password.data or '').strip()
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
        else:
            User.create(username, password, form.role.data)
            flash('User created', 'success')
            return redirect(url_for('users'))
    user_list = User.query.order_by(User.username).all()
    return render_template('users.html', form=form, user_list=user_list)

@app.route('/users/<int:user_id>/reset', methods=['POST'])
@login_required
@manager_required
def reset_pwd(user_id):
    form = ResetPwdForm()
    if form.validate_on_submit():
        user = User.query.get_or_404(user_id)
        new_pwd = (form.password.data or '').strip()
        user.pw_hash = bcrypt.hashpw(new_pwd.encode(), bcrypt.gensalt()).decode()
        db.session.commit()
        flash('Password reset', 'success')
    return redirect(url_for('users'))


@app.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@manager_required
def delete_user(user_id):
    # Prevent accidental self-deletion
    if current_user.id == user_id:
        flash('You cannot delete your own account.', 'warning')
        return redirect(url_for('users'))

    user = User.query.get_or_404(user_id)

    # Block deletion if user has shift history
    if Shift.query.filter_by(cashier_id=user.id).first():
        flash('Cannot delete: user has shift history.', 'warning')
        return redirect(url_for('users'))

    db.session.delete(user)
    db.session.commit()
    flash('User deleted', 'info')
    return redirect(url_for('users'))


@app.route('/products')
@login_required
@manager_required
def products():
    # Get sorting parameters
    sort_by = request.args.get('sort', 'name')
    sort_order = request.args.get('order', 'asc')
    search_query = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    
    # Base query
    query = Product.query
    
    # Apply search filter
    if search_query:
        query = query.filter(Product.name.ilike(f'%{search_query}%'))
    
    # Apply sorting
    sort_field = {
        'name': Product.name,
        'qty': Product.qty_at_hand,
        'price': Product.selling_price
    }.get(sort_by, Product.name)
    
    if sort_order == 'desc':
        query = query.order_by(sort_field.desc())
    else:
        query = query.order_by(sort_field.asc())
    
    # Pagination
    pagination = query.paginate(page=page, per_page=20, error_out=False)
    items = pagination.items
    
    return render_template('products.html', 
                           items=items,
                           sort_by=sort_by,
                           sort_order=sort_order,
                           search_query=search_query,
                           pagination=pagination,
                           currency=app.config['CURRENCY_SYMBOL'])

@app.route('/product/<int:pid>/edit', methods=['GET', 'POST'])
@login_required
@manager_required
def edit_product(pid):
    p = Product.query.get_or_404(pid)
    form = EditProductForm(obj=p)

    if form.validate_on_submit():
        # ① record price-change in the history table
        if form.selling_price.data != p.selling_price:
            db.session.add(PriceChange(
                product_id=p.id,
                old_price=p.selling_price,
                new_price=form.selling_price.data,
                changed_by=current_user.username
            ))
            log('price-change', f'{p.name}: {p.selling_price} ➜ {form.selling_price.data}')

        # ② apply the edits
        form.populate_obj(p)
        db.session.commit()

        flash('Product updated', 'success')
        return redirect(url_for('products'))

    return render_template('edit_product.html', form=form)



@app.route('/product/<int:pid>/delete', methods=['POST'])
@login_required
@manager_required
def delete_product(pid):
    p = Product.query.get_or_404(pid)
    from models import Sale
    if Sale.query.filter_by(product_id=p.id).first():
        flash('Cannot delete: product has sales history. Consider archiving instead.', 'warning')
        return redirect(url_for('products'))

    db.session.delete(p)
    db.session.commit()
    flash('Product deleted', 'info')
    return redirect(url_for('products'))


@app.route('/product/<int:pid>/update-qty', methods=['POST'])
@login_required
@manager_required
def update_product_qty(pid):
    """Inline adjust stock quantity from the products list.
    Accepts a 'delta' integer to add/subtract from current qty. Preserves filters.
    """
    p = Product.query.get_or_404(pid)
    # Preserve list state
    sort = request.form.get('sort')
    order = request.form.get('order')
    search = request.form.get('search')
    try:
        page = int(request.form.get('page') or 1)
    except (TypeError, ValueError):
        page = 1

    # Parse delta
    try:
        raw = request.form.get('delta')
        delta = int(raw) if raw not in (None, '') else 0
    except (TypeError, ValueError):
        flash('Enter a valid quantity adjustment.', 'warning')
        return redirect(url_for('products', sort=sort, order=order, search=search, page=page))

    if delta == 0:
        flash('No change applied.', 'info')
        return redirect(url_for('products', sort=sort, order=order, search=search, page=page))

    old_qty = int(p.qty_at_hand or 0)
    new_qty = old_qty + delta
    if new_qty < 0:
        flash('Resulting quantity cannot be negative.', 'danger')
        return redirect(url_for('products', sort=sort, order=order, search=search, page=page))

    p.qty_at_hand = new_qty
    db.session.add(LogEntry(
        user=current_user.username,
        action='adjust_stock',
        details=f"{p.name}: {old_qty} {'+' if delta >= 0 else ''}{delta} → {new_qty}"
    ))
    db.session.commit()
    flash('Inventory updated', 'success')
    return redirect(url_for('products', sort=sort, order=order, search=search, page=page))

@app.route('/sales', methods=['GET'])
@login_required          # add @manager_required if only managers may browse
def sales_list():
    #
    # ── 1. read ?date=YYYY-MM-DD, default = today ───────────────────────
    #
    sel = request.args.get('date') or date.today().isoformat()
    order = (request.args.get('order') or 'asc').lower()
    if order not in ('asc','desc'):
        order = 'asc'
    try:
        sel_date = datetime.strptime(sel, "%Y-%m-%d").date()
    except ValueError:
        abort(400)   # bad format

    #
    # ── 2. fetch that day’s sales + product info ────────────────────────
    #
    sale_id_order = Sale.id.asc() if order == 'asc' else Sale.id.desc()
    day_sales = (
        db.session.query(Sale, Product)
        .join(Product)
        .filter(func.date(Sale.date) == sel_date)   # cast to DATE if Sale.date is DateTime
        .order_by(sale_id_order)
        .all()
    )


    return render_template(
        "sales.html",
        sales=day_sales,
        sel_date=sel_date,
        today=date.today(),        # now Jinja can call today.isoformat()
        order=order
    )


@app.route('/sale/<int:sid>/edit', methods=['GET','POST'])
@login_required
def edit_sale(sid):
    sale = Sale.query.get_or_404(sid)
    form = EditSaleForm(obj=sale)

    if form.validate_on_submit():
        # Determine intended new values first
        new_qty = form.qty_sold.data
        new_unit_price = form.unit_price.data  # may be None
        new_effective = new_unit_price if new_unit_price is not None else sale.product.selling_price

        # Below-cost guard (still enforced for cashiers)
        if float(new_effective or 0) < float(sale.product.cost_price or 0):
            if current_user.role != 'manager':
                db.session.add(LogEntry(
                    user=current_user.username,
                    action='below_cost_attempt_blocked',
                    details=f"Attempted edit sale #{sale.id} {sale.product.name} @ {app.config['CURRENCY_SYMBOL']}{float(new_effective):.2f} (< cost {app.config['CURRENCY_SYMBOL']}{sale.product.cost_price:.2f})"
                ))
                db.session.commit()
                flash('Below-cost price is not allowed. Ask a manager.', 'danger')
                return render_template('edit_sale.html', form=form, sale=sale, currency=app.config['CURRENCY_SYMBOL'])
            else:
                db.session.add(LogEntry(
                    user=current_user.username,
                    action='below_cost_override',
                    details=f"Manager approved edit sale #{sale.id} {sale.product.name} @ {app.config['CURRENCY_SYMBOL']}{float(new_effective):.2f} (< cost {app.config['CURRENCY_SYMBOL']}{sale.product.cost_price:.2f})"
                ))

        # Adjust inventory based on quantity diff
        diff = new_qty - sale.qty_sold
        if diff != 0:
            db.session.add(LogEntry(
                user=current_user.username,
                action='edit_sale_qty',
                details=f"Sale #{sale.id} {sale.product.name}: qty {sale.qty_sold} → {new_qty}"
            ))
        sale.qty_sold = new_qty
        sale.product.qty_at_hand -= diff

        # Determine old effective unit price
        old_effective = sale.unit_price if sale.unit_price is not None else sale.product.selling_price

        # Apply price change
        sale.unit_price = new_unit_price

        # Audit if price changed
        if float(new_effective or 0) != float(old_effective or 0):
            db.session.add(LogEntry(
                user=current_user.username,
                action='edit_sale_price',
                details=f"Sale #{sale.id} {sale.product.name}: {app.config['CURRENCY_SYMBOL']}{old_effective:.2f} → {app.config['CURRENCY_SYMBOL']}{float(new_effective or 0):.2f}"
            ))

        db.session.commit()
        # Role-specific success message
        if current_user.role == 'cashier':
            flash('Sale updated – your manager has been notified.', 'info')
        else:
            flash('Sale updated', 'success')
        sale_date = sale.date
        return redirect(url_for('sales_list', date=sale_date.isoformat()))
    return render_template('edit_sale.html', form=form, sale=sale, currency=app.config['CURRENCY_SYMBOL'])

@app.route('/sale/<int:sid>/void', methods=['POST'])
@login_required
def void_sale(sid):
    if 'confirm' not in request.form:
        abort(400)  # safeguard against direct POST without confirmation

    sale = Sale.query.get_or_404(sid)
    
    # 1. Return stock to inventory
    sale.product.qty_at_hand += sale.qty_sold
    
    # 2. Create audit log entry
    db.session.add(LogEntry(
        user=current_user.username,
        action='void_sale',
        details=f'{sale.qty_sold} × {sale.product.name} (sale #{sale.id})'
    ))
    
    sale_date = sale.date  # save before deleting
    # 3. Delete sale record
    db.session.delete(sale)
    db.session.commit()
    
    # 4. Cashier notification
    if current_user.role == 'cashier':
        flash('Sale voided – your manager has been notified.', 'info')
    else:
        flash('Sale voided.', 'success')
    
    return redirect(url_for('sales_list', date=sale_date.isoformat()))


@app.route('/shift/open')
@login_required
def open_shift():
    if Shift.query.filter_by(cashier_id=current_user.id, closed_at=None).first():
        flash('Shift already open', 'warning')
    else:
        db.session.add(Shift(cashier_id=current_user.id))
        db.session.commit()
        log('shift-open', current_user.username)
        flash('Shift opened', 'success')
    return redirect(url_for('dashboard'))


@app.route('/shift/close', methods=['POST'])
@login_required
def close_shift():
    shift = Shift.query.filter_by(cashier_id=current_user.id, closed_at=None).first()
    if not shift:
        abort(400)
    qty, rev = (db.session.query(db.func.sum(Sale.qty_sold),
                                 db.func.sum(Sale.qty_sold*Product.selling_price))
                .join(Product)
                .filter(Sale.date >= shift.opened_at.date())
                .first())
    shift.total_qty = qty or 0
    shift.total_rev = rev or 0.0
    shift.closed_at = datetime.utcnow()
    db.session.commit()
    log('shift-close', f"{current_user.username} qty={shift.total_qty} rev={shift.total_rev}")
    flash(f'Shift closed – Qty {shift.total_qty}  Rev {shift.total_rev}', 'info')
    return redirect(url_for('dashboard'))



@app.route('/logs')
@login_required
@manager_required
def logs():
    logs = LogEntry.query.order_by(LogEntry.timestamp.desc()).limit(200).all()
    return render_template('logs.html', logs=logs)


# Version metadata injected to templates (Story 3)
@app.context_processor
def inject_app_meta():
    def _git_sha_short():
        try:
            return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode().strip()
        except Exception:
            return None
    sha_env = os.getenv('RENDER_GIT_COMMIT') or os.getenv('GIT_COMMIT')
    sha = sha_env or _git_sha_short()
    version_short = (sha[:7] if sha else 'dev')
    env = os.getenv('APP_ENV', 'Development')
    env_title = (env.title() if env else 'Development')
    owner_email = app.config.get('ERROR_REPORT_EMAIL_TO')
    return dict(app_version=version_short, app_env=env_title, owner_email=owner_email)


@app.errorhandler(429)
def ratelimit_exceeded(e):
    # Friendly rate-limit page; applies mainly to login route
    retry_after = getattr(e, 'retry_after', None)
    err_id = uuid.uuid4().hex[:8].upper()
    try:
        db.session.add(LogEntry(
            user=(current_user.username if current_user.is_authenticated else 'anon'),
            action='http_429',
            details=f"id={err_id} path={request.path} ip={request.remote_addr} ua={request.user_agent.string}"
        ))
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
    return render_template('429.html', retry_after=retry_after, error_id=err_id), 429


@app.errorhandler(500)
def internal_error(e):
    err_id = uuid.uuid4().hex[:8].upper()
    tb = ''.join(traceback.format_exception(None, e, e.__traceback__))
    # Sanitize/truncate traceback
    tb_short = (tb[:2000] + '…') if len(tb) > 2000 else tb
    try:
        db.session.add(LogEntry(
            user=(current_user.username if current_user.is_authenticated else 'anon'),
            action='server_error',
            details=f"id={err_id} path={request.path} method={request.method} ua={request.user_agent.string}\n{tb_short}"
        ))
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
    return render_template('500.html', error_id=err_id), 500


@app.route('/shifts')
@login_required
@manager_required
def shift_list():
    shifts = Shift.query.filter(Shift.closed_at.isnot(None)).order_by(Shift.closed_at.desc()).limit(200).all()
    currency = app.config['CURRENCY_SYMBOL']
    return render_template('shifts.html', shifts=shifts, currency=currency)



@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.context_processor
def inject_open_shift():
    if current_user.is_authenticated and current_user.role == 'cashier':
        open_shift = Shift.query.filter_by(cashier_id=current_user.id,
                                           closed_at=None).first()
    else:
        open_shift = None
    return dict(open_shift=open_shift)


@app.context_processor
def inject_shift_totals():
    if current_user.is_authenticated and current_user.role == 'cashier':
        shift = Shift.query.filter_by(cashier_id=current_user.id, closed_at=None).first()
        if shift:
            qty, rev = (
                db.session.query(db.func.sum(Sale.qty_sold),
                                 db.func.sum(Sale.qty_sold * Product.selling_price))
                .join(Product)
                .filter(Sale.date >= shift.opened_at.date())
                .first()
            )
        else:
            qty = rev = None
    else:
        shift = qty = rev = None
    return dict(open_shift=shift, shift_qty=qty or 0, shift_rev=rev or 0.0)

DATE_FMT = "%Y-%m-%d"
def _aggregate_sales_range(start: date, end: date):
    """Return list[dict] bucketed by *day* between start and end (inclusive)."""
    rows = (
        db.session.query(
            Sale.date.label("bucket"),
            func.sum(Sale.qty_sold).label("qty"),
            func.sum(
                Sale.qty_sold *
                func.coalesce(Sale.unit_price, Product.selling_price)
            ).label("rev"),
            func.sum(Sale.qty_sold * Product.cost_price).label("cost")
        )
        .join(Product)
        .filter(Sale.date.between(start, end))
        .group_by(Sale.date)
        .order_by(Sale.date)
        .all()
    )
    return [dict(bucket=r.bucket, qty=r.qty, rev=float(r.rev), cost=float(r.cost))
            for r in rows]

def _sales_between(start: date, end: date):
    """Return list[dict] bucketed by day within [start, end]."""
    rows = (
        db.session.query(
            Sale.date.label("bucket"),
            func.sum(Sale.qty_sold).label("qty"),
            func.sum(
                Sale.qty_sold *
                func.coalesce(Sale.unit_price, Product.selling_price)
            ).label("rev"),
            func.sum(Sale.qty_sold * Product.cost_price).label("cost"))
        .join(Product)
        .filter(Sale.date.between(start, end))
        .group_by("bucket")
        .order_by("bucket")
        .all()
    )
    return [dict(bucket=r.bucket, qty=r.qty,
                 rev=float(r.rev), cost=float(r.cost)) for r in rows]


@app.route("/reports/sales-summary")
@login_required
@manager_required
def sales_summary():

    # ── 1. Parse date-range  ───────────────────────────────────────────
    try:
        start = datetime.strptime(request.args.get("start"), DATE_FMT).date()
        end   = datetime.strptime(request.args.get("end"),   DATE_FMT).date()
    except (TypeError, ValueError):
        # fallback to current month-to-date
        today = date.today()
        start = today.replace(day=1)
        end   = today

    if start > end:                              # auto-swap accidental order
        start, end = end, start

    # ── 2. Other query-string controls  ────────────────────────────────
    breakdown = request.args.get("breakdown", "summary")     # summary|category|product
    export    = request.args.get("export")                   # csv|xlsx

    # ── 3. Aggregate once per day inside the range  ────────────────────
    rows = _aggregate_sales_range(start, end)                # list of dicts
    gp_data = [{
        **r,
        "gp": r["rev"] - r["cost"]
    } for r in rows]

    # ── 4. Derive view-specific tables / charts  ───────────────────────
    if breakdown == "category":
        view_rows = (
            db.session.query(
                Product.category,
                func.sum(
                    Sale.qty_sold * func.coalesce(Sale.unit_price, Product.selling_price)
                ).label("rev")
            )
            .join(Product)
            .filter(Sale.date.between(start, end))
            .group_by(Product.category)
            .all()
        )
        chart_labels = [c or 'Uncategorized' for c, _ in view_rows]
        chart_values = [float(r or 0) for _, r in view_rows]

    elif breakdown == "product":
        view_rows = (
            db.session.query(
                Product.name,
                func.sum(Sale.qty_sold).label("qty"),
                func.sum(
                    Sale.qty_sold * func.coalesce(Sale.unit_price, Product.selling_price)
                ).label("rev"),
            )
            .join(Product)
            .filter(Sale.date.between(start, end))
            .group_by(Product.name)
            .order_by(
                func.sum(
                    Sale.qty_sold * func.coalesce(Sale.unit_price, Product.selling_price)
                ).desc()
            )
            .limit(50)
            .all()
        )
        chart_labels = [n for n, _, _ in view_rows][:10]
        chart_values = [float(r or 0) for _, _, r in view_rows][:10]

    else:                                          # summary
        view_rows    = gp_data
        chart_labels = [r["bucket"] for r in gp_data]
        chart_values = [r["rev"]   for r in gp_data]

    # ── 5. CSV/XLSX export (same range & breakdown)  ───────────────────
    if export == "csv":
        df = pd.DataFrame(view_rows)
        filename = f"sales_{breakdown}_{start}_{end}.csv"
        return send_file(BytesIO(df.to_csv(index=False).encode()),
                         "text/csv",
                         download_name=filename,
                         as_attachment=True)
    if export == "xlsx":
        df = pd.DataFrame(view_rows)
        xbuf = BytesIO()
        df.to_excel(xbuf, index=False)
        xbuf.seek(0)
        filename = f"sales_{breakdown}_{start}_{end}.xlsx"
        return send_file(xbuf,
                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         download_name=filename,
                         as_attachment=True)

    # ── 6. Render template  ────────────────────────────────────────────
    return render_template(
        "sales_summary.html",
        start=start, end=end,
        breakdown=breakdown,
        data=gp_data,
        rows=view_rows,
        chart_labels=chart_labels,
        chart_values=chart_values,
        currency=app.config["CURRENCY_SYMBOL"]
    )


@app.route('/reports/inventory')
@login_required 
@manager_required
def inventory_report():
    items = (
        db.session.query(Product,
                         (Product.qty_at_hand*Product.cost_price).label('cost_val'),
                         (Product.qty_at_hand*Product.selling_price).label('sell_val'))
        .order_by(Product.name)
        .all())
    totals = {
        'cost':  sum(r.cost_val  for r in items),
        'sell':  sum(r.sell_val for r in items),
    }
    return render_template('inventory_report.html',
                           items=items, totals=totals,
                           currency=app.config['CURRENCY_SYMBOL'])

# ────────────────────────────────────────────────────────────────
# Settings – admin only
# ────────────────────────────────────────────────────────────────

from flask_wtf import FlaskForm
from wtforms import SubmitField

class ResetAllForm(FlaskForm):
    submit = SubmitField('RESET ALL')


def _inventory_dataframe():
    data = [{
        'id': p.id,
        'name': p.name,
        'category': p.category,
        'expiry_date': p.expiry_date,
        'cost_price': p.cost_price,
        'selling_price': p.selling_price,
        'initial_qty': p.initial_qty,
        'qty_at_hand': p.qty_at_hand,
        'safety_stock': p.safety_stock,
    } for p in Product.query.order_by(Product.name)]
    return pd.DataFrame(data)


def _sales_dataframe():
    rows = (
        db.session.query(Sale, Product.name)
        .join(Product)
        .order_by(Sale.date.desc())
        .all()
    )
    data = [{
        'id': s.id,
        'product_id': s.product_id,
        'product_name': name,
        'date': s.date,
        'qty_sold': s.qty_sold,
        'unit_price': s.unit_price or s.product.selling_price,
    } for s, name in rows]
    return pd.DataFrame(data)


@app.route('/settings')
@login_required
@manager_required
def settings():
    form = ResetAllForm()
    return render_template('settings.html', form=form)


@app.route('/settings/download/<string:kind>')
@login_required
@manager_required

def download_data(kind):
    if kind == 'inventory':
        df = _inventory_dataframe()
        filename = 'inventory_backup.csv'
    elif kind == 'sales':
        df = _sales_dataframe()
        filename = 'sales_backup.csv'
    else:
        abort(404)

    return send_file(
        BytesIO(df.to_csv(index=False).encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename,
    )


@app.route('/settings/reset', methods=['POST'])
@login_required
@manager_required

def reset_all():
    form = ResetAllForm()
    if not form.validate_on_submit():
        flash('Invalid form submission', 'danger')
        return redirect(url_for('settings'))

    

    # perform destructive wipe inside transaction
    try:
        n_sales = Sale.query.delete()
        PriceChange.query.delete()
        Shift.query.delete()
        n_products = Product.query.delete()

        db.session.add(LogEntry(
            user=current_user.username,
            action='reset_all',
            details=f'removed {n_products} products and {n_sales} sales'
        ))
        db.session.commit()
        flash('All sales and inventory data have been cleared.', 'warning')
    except Exception as e:
        db.session.rollback()
        app.logger.exception('Reset failed')
        flash('Reset failed: ' + str(e), 'danger')
    return redirect(url_for('dashboard'))

 
 
if __name__ == '__main__':
    # Ensure tables exist when running via `python app.py` as well
    with app.app_context():
        db.create_all()
    app.run(debug=True)