from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, FloatField, DateField, SelectField, SubmitField
from wtforms.validators import DataRequired, NumberRange

class AddStockForm(FlaskForm):
    name = StringField('Product name', validators=[DataRequired()])
    category = StringField('Category')
    expiry_date = DateField('Expiry date', format='%Y-%m-%d')
    cost_price = FloatField('Cost price', validators=[NumberRange(min=0.01)])
    selling_price = FloatField('Selling price', validators=[NumberRange(min=0.01)])
    quantity = IntegerField('Quantity', validators=[NumberRange(min=1)])
    submit = SubmitField('Add / Restock')

class RecordSaleForm(FlaskForm):
    product_id = SelectField('Product')  # choices filled in route
    quantity = IntegerField('Quantity sold', validators=[NumberRange(min=1)])
    submit = SubmitField('Record Sale')