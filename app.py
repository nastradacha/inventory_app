from flask import Flask, render_template, redirect, url_for, flash, request, abort, session
from flask_login import LoginManager, login_user, login_required, current_user, logout_user
from flask_wtf import CSRFProtect 
from functools import wraps
import bcrypt 
from forms import LoginForm 

from datetime import date, datetime
from config import Config
from models import db, Product, Sale, User
from forms import AddStockForm, RecordSaleForm, NewUserForm, ResetPwdForm, EditProductForm
from rapidfuzz import fuzz


app = Flask(__name__)
app.config.from_object(Config)

# Enable CSRF protection for every POST form
csrf = CSRFProtect(app)

db.init_app(app)

# --- database setup -------------------------------------------------------
# Flask 3.0 removed the before_first_request decorator. We now create the
# tables once at startup, inside an application context.
with app.app_context():
    db.create_all()
# -------------------------------------------------------------------------

@app.route('/')
def dashboard():
    products = Product.query.all()
    total_cost = sum(p.qty_at_hand * p.cost_price for p in products)
    total_value = sum(p.qty_at_hand * p.selling_price for p in products)
    total_profit = total_value - total_cost
    low_stock = [p for p in products if p.qty_at_hand < 5]
    top_sales = (
        db.session.query(Product.name, db.func.sum(Sale.qty_sold).label('units'))
        .join(Sale)
        .group_by(Product.name)
        .order_by(db.desc('units'))
        .limit(5)
        .all()
    )
    currency = app.config['CURRENCY_SYMBOL']
    return render_template('dashboard.html', **locals())

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
        else:  # new product
            p = Product(
                name=form.name.data,
                category=form.category.data,
                expiry_date=form.expiry_date.data,
                cost_price=form.cost_price.data,
                selling_price=form.selling_price.data,
                initial_qty=form.quantity.data,
                qty_at_hand=form.quantity.data,
            )
            db.session.add(p)
        db.session.commit()
        flash('Stock updated!', 'success')
        return redirect(url_for('dashboard'))

    # This return only runs if form fails validation
    return render_template('add_stock.html', form=form, all_names=[])



@app.route('/record-sale', methods=['GET', 'POST'])
def record_sale():
    form = RecordSaleForm()
    form.product_id.choices = [
        (p.id, p.name) for p in Product.query.order_by(Product.name)
    ]
    if form.validate_on_submit():
        product = Product.query.get(int(form.product_id.data))
        if product.qty_at_hand < form.quantity.data:
            flash('Not enough stock!', 'danger')
        else:
            product.qty_at_hand -= form.quantity.data
            sale = Sale(
                product_id=product.id,
                qty_sold=form.quantity.data,
                date=date.today(),
            )
            db.session.add(sale)
            db.session.commit()
            flash('Sale recorded.', 'success')
            return redirect(url_for('dashboard'))
    return render_template('record_sale.html', form=form)


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


@app.route('/login', methods=['GET', 'POST'])
@csrf.exempt                              # allow login even if token missing (fallback)
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and bcrypt.checkpw(form.password.data.encode(), user.pw_hash.encode()):
            login_user(user)
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
            p = Product.query.filter_by(name=form_data['name']).first()
            if p:
                p.qty_at_hand += int(form_data['quantity'])
                p.initial_qty += int(form_data['quantity'])
            else:
                p = Product(
                    name=form_data['name'],
                    category=form_data['category'],
                    expiry_date=form_data['expiry_date'],
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
        if User.query.filter_by(username=form.username.data).first():
            flash('Username already exists', 'danger')
        else:
            User.create(form.username.data, form.password.data, form.role.data)
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
        user.pw_hash = bcrypt.hashpw(form.password.data.encode(), bcrypt.gensalt()).decode()
        db.session.commit()
        flash('Password reset', 'success')
    return redirect(url_for('users'))



@app.route('/products')
@login_required
@manager_required
def products():
    items = Product.query.order_by(Product.name).all()
    return render_template('products.html', items=items)

@app.route('/product/<int:pid>/edit', methods=['GET','POST'])
@login_required
@manager_required
def edit_product(pid):
    p = Product.query.get_or_404(pid)
    form = EditProductForm(obj=p)
    if form.validate_on_submit():
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
    db.session.delete(p)
    db.session.commit()
    flash('Product deleted', 'info')
    return redirect(url_for('products'))



@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))



if __name__ == '__main__':
    # Ensure tables exist when running via `python app.py` as well
    with app.app_context():
        db.create_all()
    app.run(debug=True)