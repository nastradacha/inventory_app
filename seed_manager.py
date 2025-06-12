from app import app, db          # app object & db come from app.py
from models import User         # User model comes from models.

with app.app_context():
    # username, password, role
    User.create('admin', 'changeme', 'manager')
    print('Admin account created!')