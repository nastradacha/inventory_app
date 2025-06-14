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
    safety_stock = IntegerField('Safety stock (re-order level)',
                                default=5,
                                validators=[NumberRange(min=0)])

class RecordSaleForm(FlaskForm):
    product_id = SelectField('Product')  # choices filled in route
    quantity = IntegerField('Quantity sold', validators=[NumberRange(min=1)])
    submit = SubmitField('Record Sale')

class NewUserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = StringField('Password', validators=[DataRequired()])
    role = SelectField('Role', choices=[('manager','Manager'),('cashier','Cashier')])
    submit = SubmitField('Create User')

class ResetPwdForm(FlaskForm):
    password = StringField('New Password', validators=[DataRequired()])
    submit = SubmitField('Reset')

class EditProductForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    category = StringField('Category')
    expiry_date = DateField('Expiry', format='%Y-%m-%d')
    cost_price = FloatField('Cost', validators=[NumberRange(min=0.01)])
    selling_price = FloatField('Selling', validators=[NumberRange(min=0.01)])
    submit = SubmitField('Save')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = StringField('Password', validators=[DataRequired()])
    submit   = SubmitField('Sign In')

class EditSaleForm(FlaskForm):
    qty_sold = IntegerField('Quantity', validators=[NumberRange(min=1)])
    submit   = SubmitField('Save')