from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
import bcrypt
from datetime import date
from sqlalchemy import func, Index

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

    __table_args__ = (
        Index(
            'ix_product_name_ci',          # index name
            func.lower(name),              # functional expression
            unique=True                    # enforce uniqueness
        ),
    )

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    date = db.Column(db.Date, default=date.today, nullable=False)
    qty_sold = db.Column(db.Integer, nullable=False)

    product = db.relationship('Product', backref=db.backref('sales', lazy=True))


class User(UserMixin, db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    pw_hash  = db.Column(db.String(128), nullable=False)
    role     = db.Column(db.String(20), nullable=False)  # 'manager' or 'cashier'

    @staticmethod
    def create(username, password, role):
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user = User(username=username, pw_hash=pw_hash, role=role)
        db.session.add(user)
        db.session.commit()