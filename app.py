from flask import Flask, render_template, redirect, url_for, flash
from datetime import date
from config import Config
from models import db, Product, Sale
from forms import AddStockForm, RecordSaleForm

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

@app.before_first_request
def create_tables():
    db.create_all()

@app.route('/')
def dashboard():
    products = Product.query.all()
    total_cost = sum(p.qty_at_hand * p.cost_price for p in products)
    total_value = sum(p.qty_at_hand * p.selling_price for p in products)
    total_profit = total_value - total_cost
    low_stock = [p for p in products if p.qty_at_hand < 5]
    top_sales = (db.session.query(Product.name, db.func.sum(Sale.qty_sold).label('units'))
                 .join(Sale).group_by(Product.name).order_by(db.desc('units')).limit(5).all())
    return render_template('dashboard.html', **locals())

@app.route('/add-stock', methods=['GET', 'POST'])
def add_stock():
    form = AddStockForm()
    if form.validate_on_submit():
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
                qty_at_hand=form.quantity.data
            )
            db.session.add(p)
        db.session.commit()
        flash('Stock updated!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('add_stock.html', form=form)

@app.route('/record-sale', methods=['GET', 'POST'])
def record_sale():
    form = RecordSaleForm()
    form.product_id.choices = [(p.id, p.name) for p in Product.query.order_by(Product.name)]
    if form.validate_on_submit():
        product = Product.query.get(int(form.product_id.data))
        if product.qty_at_hand < form.quantity.data:
            flash('Not enough stock!', 'danger')
        else:
            product.qty_at_hand -= form.quantity.data
            sale = Sale(product_id=product.id, qty_sold=form.quantity.data, date=date.today())
            db.session.add(sale)
            db.session.commit()
            flash('Sale recorded.', 'success')
            return redirect(url_for('dashboard'))
    return render_template('record_sale.html', form=form)

if __name__ == '__main__':
    app.run(debug=True)