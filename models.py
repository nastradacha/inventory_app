from flask_sqlalchemy import SQLAlchemy
from datetime import date

db = SQLAlchemy()

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    category = db.Column(db.String(120))
    expiry_date = db.Column(db.Date)
    cost_price = db.Column(db.Float, nullable=False)
    selling_price = db.Column(db.Float, nullable=False)
    initial_qty = db.Column(db.Integer, nullable=False)
    qty_at_hand = db.Column(db.Integer, nullable=False)

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    date = db.Column(db.Date, default=date.today, nullable=False)
    qty_sold = db.Column(db.Integer, nullable=False)

    product = db.relationship('Product', backref=db.backref('sales', lazy=True))