from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, send_file
from werkzeug.utils import secure_filename
import pandas as pd
import os
from datetime import datetime
from models import db, Product, LogEntry
from forms import BatchInventoryForm
from flask_login import login_required, current_user
import io

batch_inventory_bp = Blueprint('batch_inventory', __name__)

ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_row_data(row, row_num):
    """Validate a single row of data"""
    errors = []
    
    # Check required fields
    required_fields = ['name', 'cost_price', 'selling_price', 'quantity']
    for field in required_fields:
        if field not in row or pd.isna(row[field]) or str(row[field]).strip() == '':
            errors.append(f"Row {row_num}: {field} is required")
    
    # Validate numeric fields
    numeric_fields = ['cost_price', 'selling_price', 'quantity', 'safety_stock']
    for field in numeric_fields:
        if field in row and not pd.isna(row[field]):
            try:
                value = float(str(row[field]).replace('GH₵', '').replace(',', ''))
                if value < 0:
                    errors.append(f"Row {row_num}: {field} must be positive")
            except ValueError:
                errors.append(f"Row {row_num}: {field} must be a valid number")
    
    # Validate quantity is integer
    if 'quantity' in row and not pd.isna(row['quantity']):
        try:
            qty = int(float(str(row['quantity']).replace(',', '')))
            if qty < 0:
                errors.append(f"Row {row_num}: quantity must be positive")
        except ValueError:
            errors.append(f"Row {row_num}: quantity must be a whole number")
    
    return errors

def process_spreadsheet(file, update_mode):
    """Process uploaded spreadsheet and return preview data"""
    try:
        # Read file based on extension
        filename = file.filename.lower()
        if filename.endswith('.csv'):
            df = pd.read_csv(file)
        elif filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file)
        else:
            return {'success': False, 'message': 'Invalid file format'}
        
        # Standardize column names
        column_mapping = {
            'name': ['name', 'product_name', 'product', 'item'],
            'category': ['category', 'type', 'group'],
            'cost_price': ['cost_price', 'cost', 'buy_price', 'purchase_price'],
            'selling_price': ['selling_price', 'sell_price', 'price', 'retail_price'],
            'quantity': ['quantity', 'stock', 'qty', 'amount'],
            'safety_stock': ['safety_stock', 'reorder_level', 'minimum_stock'],
            'expiry_date': ['expiry_date', 'expiry', 'expires']
        }
        
        # Find matching columns
        standardized_df = pd.DataFrame()
        for standard_name, possible_names in column_mapping.items():
            for col in df.columns:
                if col.lower().strip() in [name.lower() for name in possible_names]:
                    standardized_df[standard_name] = df[col]
                    break
        
        # Fill missing columns with defaults
        if 'safety_stock' not in standardized_df.columns:
            standardized_df['safety_stock'] = 5
        if 'category' not in standardized_df.columns:
            standardized_df['category'] = 'General'
        
        # Process each row
        results = []
        errors = []
        
        for idx, row in standardized_df.iterrows():
            row_num = idx + 2  # +1 for header, +1 for 1-based indexing
            
            # Validate row
            row_errors = validate_row_data(row, row_num)
            if row_errors:
                errors.extend(row_errors)
                continue
            
            # Clean data
            name = str(row['name']).strip()
            category = str(row.get('category', 'General')).strip()
            cost_price = float(str(row['cost_price']).replace('GH₵', '').replace(',', ''))
            selling_price = float(str(row['selling_price']).replace('GH₵', '').replace(',', ''))
            quantity = int(float(str(row['quantity']).replace(',', '')))
            safety_stock = int(float(str(row.get('safety_stock', 5))))
            
            # Handle expiry date
            expiry_date = None
            if 'expiry_date' in row and not pd.isna(row['expiry_date']):
                try:
                    expiry_date = pd.to_datetime(row['expiry_date']).date()
                except:
                    pass
            
            # Check if product exists
            existing_product = Product.query.filter(
                db.func.lower(Product.name) == name.lower()
            ).first()
            
            action_type = 'update' if existing_product else 'create'
            
            # Calculate changes based on update mode
            if existing_product:
                if update_mode == 'add_stock':
                    new_quantity = existing_product.qty_at_hand + quantity
                elif update_mode == 'replace_stock':
                    new_quantity = quantity
                else:
                    new_quantity = existing_product.qty_at_hand
                
                old_cost = existing_product.cost_price
                old_selling = existing_product.selling_price
                old_quantity = existing_product.qty_at_hand
            else:
                new_quantity = quantity
                old_cost = old_selling = old_quantity = None
            
            results.append({
                'row_num': row_num,
                'action_type': action_type,
                'name': name,
                'category': category,
                'cost_price': cost_price,
                'selling_price': selling_price,
                'quantity': quantity,
                'new_quantity': new_quantity,
                'safety_stock': safety_stock,
                'expiry_date': expiry_date,
                'old_cost': old_cost,
                'old_selling': old_selling,
                'old_quantity': old_quantity,
                'existing_product': existing_product
            })
        
        return {
            'success': True,
            'results': results,
            'errors': errors,
            'total_rows': len(df),
            'valid_rows': len(results),
            'error_rows': len(errors)
        }
        
    except Exception as e:
        return {'success': False, 'message': str(e)}

@batch_inventory_bp.route('/batch-inventory', methods=['GET', 'POST'])
@login_required
def batch_inventory():
    if current_user.role != 'manager':
        flash('Access denied. Manager privileges required.', 'error')
        return redirect(url_for('dashboard'))
    form = BatchInventoryForm()
    return render_template('batch_inventory.html', form=form)

@batch_inventory_bp.route('/batch-inventory/preview', methods=['POST'])
@login_required
def preview_batch_upload():
    if current_user.role != 'manager':
        return jsonify({'error': 'Access denied. Manager privileges required.'}), 403
    if 'spreadsheet_file' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded'})
    
    file = request.files['spreadsheet_file']
    update_mode = request.form.get('update_mode', 'add_stock')
    
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'})
    
    if file and allowed_file(file.filename):
        result = process_spreadsheet(file, update_mode)
        
        if result['success']:
            return jsonify({
                'success': True,
                'html': render_template('batch_preview.html', **result)
            })
        else:
            return jsonify(result)
    
    return jsonify({'success': False, 'message': 'Invalid file type'})

@batch_inventory_bp.route('/batch-inventory/confirm', methods=['POST'])
@login_required
def confirm_batch_upload():
    if current_user.role != 'manager':
        return jsonify({'error': 'Access denied. Manager privileges required.'}), 403
    try:
        data = request.get_json()
        updates = data.get('updates', [])
        update_mode = data.get('update_mode', 'add_stock')
        
        success_count = 0
        error_count = 0
        
        # Start transaction
        db.session.begin()
        
        for update in updates:
            try:
                if update['action_type'] == 'create':
                    # Create new product
                    product = Product(
                        name=update['name'],
                        category=update['category'],
                        cost_price=update['cost_price'],
                        selling_price=update['selling_price'],
                        initial_qty=update['quantity'],
                        qty_at_hand=update['quantity'],
                        safety_stock=update['safety_stock'],
                        expiry_date=update['expiry_date']
                    )
                    db.session.add(product)
                    
                    # Log the creation
                    log_entry = LogEntry(
                        user=current_user.username,
                        action='batch_create_product',
                        details=f"Created product: {update['name']} with quantity {update['quantity']}"
                    )
                    db.session.add(log_entry)
                    
                elif update['action_type'] == 'update':
                    # Update existing product
                    product = Product.query.filter(
                        db.func.lower(Product.name) == update['name'].lower()
                    ).first()
                    
                    if product:
                        # Store old values for logging
                        old_cost = product.cost_price
                        old_selling = product.selling_price
                        old_quantity = product.qty_at_hand
                        
                        # Apply changes based on update mode
                        if update_mode in ['add_stock', 'replace_stock', 'full_update']:
                            product.qty_at_hand = update['new_quantity']
                        
                        if update_mode in ['update_prices', 'full_update']:
                            product.cost_price = update['cost_price']
                            product.selling_price = update['selling_price']
                        
                        if update_mode == 'full_update':
                            product.category = update['category']
                            product.expiry_date = update['expiry_date']
                            product.safety_stock = update['safety_stock']
                        
                        # Log the update
                        changes = []
                        if old_cost != update['cost_price']:
                            changes.append(f"cost: GH₵{old_cost} → GH₵{update['cost_price']}")
                        if old_selling != update['selling_price']:
                            changes.append(f"selling: GH₵{old_selling} → GH₵{update['selling_price']}")
                        if old_quantity != update['new_quantity']:
                            changes.append(f"quantity: {old_quantity} → {update['new_quantity']}")
                        
                        log_entry = LogEntry(
                            user=current_user.username,
                            action='batch_update_product',
                            details=f"Updated {update['name']}: {', '.join(changes)}"
                        )
                        db.session.add(log_entry)
                
                success_count += 1
                
            except Exception as e:
                error_count += 1
                continue
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Successfully processed {success_count} products.',
            'success_count': success_count,
            'error_count': error_count
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': str(e)
        })

@batch_inventory_bp.route('/batch-inventory/download-template/<format>')
@login_required
def download_batch_template(format):
    if current_user.role != 'manager':
        flash('Access denied. Manager privileges required.', 'error')
        return redirect(url_for('dashboard'))
    """Download template spreadsheet"""
    template_data = [
        {
            'name': 'Milo 500g',
            'category': 'Beverages',
            'cost_price': '12.50',
            'selling_price': '15.00',
            'quantity': '50',
            'safety_stock': '10',
            'expiry_date': '31/12/2025'
        },
        {
            'name': 'Peak Milk 170g',
            'category': 'Dairy',
            'cost_price': '8.00',
            'selling_price': '10.00',
            'quantity': '30',
            'safety_stock': '5',
            'expiry_date': '15/06/2025'
        },
        {
            'name': 'Indomie Chicken',
            'category': 'Food',
            'cost_price': '3.50',
            'selling_price': '4.50',
            'quantity': '100',
            'safety_stock': '20',
            'expiry_date': ''
        }
    ]
    
    df = pd.DataFrame(template_data)

    # If CSV requested or openpyxl not available, serve CSV
    if format.lower() == 'csv':
        csv_bytes = df.to_csv(index=False).encode()
        return send_file(
            io.BytesIO(csv_bytes),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'inventory_template_{datetime.now().strftime("%Y%m%d")}.csv'
        )

    # Otherwise try to serve Excel
    try:
        import openpyxl  # noqa: F401 – required by pandas
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Inventory Template')
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue()),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'inventory_template_{datetime.now().strftime("%Y%m%d")}.xlsx'
        )
    except ModuleNotFoundError:
        # openpyxl not installed on server – fall back to CSV
        csv_bytes = df.to_csv(index=False).encode()
        return send_file(
            io.BytesIO(csv_bytes),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'inventory_template_{datetime.now().strftime("%Y%m%d")}.csv'
        )

@batch_inventory_bp.route('/batch-inventory/download-example')
@login_required
def download_example_data():
    if current_user.role != 'manager':
        flash('Access denied. Manager privileges required.', 'error')
        return redirect(url_for('dashboard'))
    """Download example with real store data"""
    # Get current products as examples
    products = Product.query.limit(10).all()
    
    example_data = []
    for product in products:
        example_data.append({
            'name': product.name,
            'category': product.category or 'General',
            'cost_price': str(product.cost_price),
            'selling_price': str(product.selling_price),
            'quantity': str(product.qty_at_hand),
            'safety_stock': str(product.safety_stock),
            'expiry_date': product.expiry_date.strftime('%d/%m/%Y') if product.expiry_date else ''
        })
    
    if not example_data:
        # Fallback to template if no products exist
        return download_batch_template()
    
    df = pd.DataFrame(example_data)

    if request.args.get('format','xlsx').lower() == 'csv':
        csv_bytes = df.to_csv(index=False).encode()
        return send_file(io.BytesIO(csv_bytes),
                         mimetype='text/csv',
                         as_attachment=True,
                         download_name=f'inventory_example_{datetime.now().strftime("%Y%m%d")}.csv')
    try:
        import openpyxl  # noqa: F401
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Example Data')
        output.seek(0)
        return send_file(io.BytesIO(output.getvalue()),
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True,
                         download_name=f'inventory_example_{datetime.now().strftime("%Y%m%d")}.xlsx')
    except ModuleNotFoundError:
        csv_bytes = df.to_csv(index=False).encode()
        return send_file(io.BytesIO(csv_bytes),
                         mimetype='text/csv',
                         as_attachment=True,
                         download_name=f'inventory_example_{datetime.now().strftime("%Y%m%d")}.csv')
