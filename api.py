from flask import Flask, request, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, MeterReading, Payment, ElectricityRate, WaterBill
from datetime import datetime
import os
from dotenv import load_dotenv
import stripe
from werkzeug.utils import secure_filename
from PIL import Image
import jwt
from functools import wraps
from flask_cors import CORS
import random
import string

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for API
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///rentmanager.db')
app.config['UPLOAD_FOLDER'] = 'static/uploads'
stripe.api_key = os.getenv('STRIPE_API_KEY')

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Token verification decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                return jsonify({'error': 'Invalid token'}), 401
        except:
            return jsonify({'error': 'Invalid token'}), 401
        
        return f(current_user, *args, **kwargs)
    
    return decorated

@app.route('/api/login', methods=['POST'])
def login():
    if not request.is_json:
        return jsonify({'error': 'Missing JSON in request'}), 400
    
    data = request.get_json()
    tenant_id = data.get('tenant_id')
    password = data.get('password')
    
    if not tenant_id or not password:
        return jsonify({'error': 'Missing tenant_id or password'}), 400
    
    # Try to find user by tenant_id first (for tenants)
    user = User.query.filter_by(tenant_id=tenant_id).first()
    if not user:
        # If not found, try email (for owner)
        user = User.query.filter_by(email=tenant_id).first()
    
    if user and user.check_password(password):
        # Generate token
        token = jwt.encode({
            'user_id': user.id,
            'is_owner': user.is_owner,
            'exp': datetime.utcnow() + datetime.timedelta(days=1)
        }, app.config['SECRET_KEY'], algorithm='HS256')
        
        return jsonify({
            'token': token,
            'user': {
                'id': user.id,
                'name': user.name,
                'is_owner': user.is_owner,
                'tenant_id': user.tenant_id if not user.is_owner else None
            }
        })
    
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/tenant/dashboard', methods=['GET'])
@token_required
def tenant_dashboard(current_user):
    if current_user.is_owner:
        return jsonify({'error': 'Owner account cannot access tenant dashboard'}), 403
    
    # Get the latest reading
    latest_reading = MeterReading.query.filter_by(user_id=current_user.id).order_by(MeterReading.reading_date.desc()).first()
    
    # Get latest electricity reading
    latest_electricity_reading = MeterReading.query.filter_by(
        user_id=current_user.id,
        meter_type='electricity'
    ).order_by(MeterReading.reading_date.desc()).first()
    
    # Get latest water reading and bill
    latest_water_reading = MeterReading.query.filter_by(
        user_id=current_user.id,
        meter_type='water'
    ).order_by(MeterReading.reading_date.desc()).first()
    
    water_bill = WaterBill.query.order_by(WaterBill.billing_date.desc()).first()
    
    # Get payment history
    payments = Payment.query.filter_by(user_id=current_user.id).order_by(Payment.payment_date.desc()).limit(10).all()
    
    # Check for existing payment for current billing period
    existing_payment = None
    if latest_reading:
        existing_payment = Payment.query.filter(
            Payment.user_id == current_user.id,
            Payment.payment_date >= latest_reading.reading_date
        ).order_by(Payment.payment_date.desc()).first()
    
    current_rate = ElectricityRate.query.order_by(ElectricityRate.effective_from.desc()).first()
    
    # Format data for response
    dashboard_data = {
        'tenant': {
            'name': current_user.name,
            'tenant_id': current_user.tenant_id,
            'rent_amount': current_user.rent_amount
        },
        'billing': {
            'rent': current_user.rent_amount,
            'electricity': 0,
            'water': 0,
            'total': current_user.rent_amount
        },
        'meter_readings': {
            'electricity': None,
            'water': None
        },
        'payment_status': None,
        'payment_history': []
    }
    
    # Add electricity billing data if available
    if latest_electricity_reading and current_rate:
        electricity_previous = MeterReading.query.filter(
            MeterReading.user_id == current_user.id,
            MeterReading.meter_type == 'electricity',
            MeterReading.reading_date < latest_electricity_reading.reading_date
        ).order_by(MeterReading.reading_date.desc()).first()
        
        if electricity_previous:
            consumption = latest_electricity_reading.reading_value - electricity_previous.reading_value
            electricity_bill = consumption * current_rate.rate_per_unit
            dashboard_data['billing']['electricity'] = electricity_bill
            dashboard_data['billing']['total'] += electricity_bill
            
            dashboard_data['meter_readings']['electricity'] = {
                'current': latest_electricity_reading.reading_value,
                'previous': electricity_previous.reading_value,
                'consumption': consumption,
                'date': latest_electricity_reading.reading_date.isoformat(),
                'has_image': bool(latest_electricity_reading.image_path),
                'image_url': f"/static/uploads/{latest_electricity_reading.image_path}" if latest_electricity_reading.image_path else None
            }
    
    # Add water billing data if available
    if latest_water_reading:
        water_previous = MeterReading.query.filter(
            MeterReading.user_id == current_user.id,
            MeterReading.meter_type == 'water',
            MeterReading.reading_date < latest_water_reading.reading_date
        ).order_by(MeterReading.reading_date.desc()).first()
        
        dashboard_data['meter_readings']['water'] = {
            'current': latest_water_reading.reading_value,
            'previous': water_previous.reading_value if water_previous else None,
            'date': latest_water_reading.reading_date.isoformat(),
            'has_image': bool(latest_water_reading.image_path),
            'image_url': f"/static/uploads/{latest_water_reading.image_path}" if latest_water_reading.image_path else None
        }
    
    if water_bill:
        dashboard_data['billing']['water'] = water_bill.amount_per_tenant
        dashboard_data['billing']['total'] += water_bill.amount_per_tenant
    
    # Add existing payment data
    if existing_payment:
        dashboard_data['payment_status'] = {
            'status': existing_payment.status,
            'amount': existing_payment.amount,
            'method': existing_payment.payment_method,
            'date': existing_payment.payment_date.isoformat(),
            'reference': existing_payment.transaction_reference or existing_payment.stripe_payment_id
        }
    
    # Format payment history
    for payment in payments:
        dashboard_data['payment_history'].append({
            'id': payment.id,
            'date': payment.payment_date.isoformat(),
            'amount': payment.amount,
            'method': payment.payment_method,
            'status': payment.status,
            'reference': payment.transaction_reference or payment.stripe_payment_id
        })
    
    return jsonify(dashboard_data)

# Add more API endpoints for other functionality...

@app.route('/api/create_payment', methods=['POST'])
@token_required
def create_payment(current_user):
    if not request.is_json:
        return jsonify({'error': 'Missing JSON in request'}), 400
    
    data = request.get_json()
    payment_method = data.get('payment_method')
    
    if not payment_method or payment_method not in ['card', 'bank_transfer', 'cash']:
        return jsonify({'error': 'Invalid payment method'}), 400
    
    # Calculate total amount due
    total_amount = current_user.rent_amount
    electricity_cost = 0
    water_cost = 0
    
    # Get latest electricity reading and calculate cost
    latest_electricity = MeterReading.query.filter_by(
        user_id=current_user.id,
        meter_type='electricity'
    ).order_by(MeterReading.reading_date.desc()).first()
    
    current_rate = ElectricityRate.query.order_by(ElectricityRate.effective_from.desc()).first()
    
    if latest_electricity and current_rate:
        previous_electricity = MeterReading.query.filter(
            MeterReading.user_id == current_user.id,
            MeterReading.meter_type == 'electricity',
            MeterReading.reading_date < latest_electricity.reading_date
        ).order_by(MeterReading.reading_date.desc()).first()
        
        if previous_electricity:
            consumption = latest_electricity.reading_value - previous_electricity.reading_value
            electricity_cost = consumption * current_rate.rate_per_unit
            total_amount += electricity_cost
    
    # Add water bill if available
    water_bill = WaterBill.query.order_by(WaterBill.billing_date.desc()).first()
    if water_bill:
        water_cost = water_bill.amount_per_tenant
        total_amount += water_cost
    
    # Create payment record
    payment = Payment(
        user_id=current_user.id,
        amount=total_amount,
        rent_component=current_user.rent_amount,
        electricity_component=electricity_cost,
        water_component=water_cost,
        payment_date=datetime.now(),
        payment_method=payment_method,
        status='pending'
    )
    
    if payment_method == 'card':
        try:
            payment_intent = stripe.PaymentIntent.create(
                amount=int(total_amount * 100),  # Convert to cents
                currency='inr',
                metadata={'user_id': current_user.id}
            )
            payment.stripe_payment_id = payment_intent.id
            db.session.add(payment)
            db.session.commit()
            
            return jsonify({
                'clientSecret': payment_intent.client_secret,
                'amount': total_amount
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 400
    else:
        # For cash and bank transfer
        reference = f"RENT{datetime.now().strftime('%Y%m%d%H%M%S')}{current_user.id}"
        payment.transaction_reference = reference
        db.session.add(payment)
        db.session.commit()
        
        return jsonify({
            'reference': reference,
            'amount': total_amount,
            'message': f'Please use reference {reference} when making the payment'
        })

def generate_tenant_password(length=8):
    """Generate a random password for tenant"""
    characters = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(random.choice(characters) for _ in range(length))
    return password

@app.route('/api/register_tenant', methods=['POST'])
@token_required
def register_tenant(current_user):
    if not current_user.is_owner:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if not request.is_json:
        return jsonify({'error': 'Missing JSON in request'}), 400
    
    data = request.get_json()
    name = data.get('name')
    rent_amount = float(data.get('rent_amount'))
    initial_electricity_reading = float(data.get('initial_electricity_reading'))
    initial_water_reading = float(data.get('initial_water_reading'))
    
    if not all([name, rent_amount, initial_electricity_reading, initial_water_reading]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Generate unique tenant ID
    tenant_id = User.generate_unique_tenant_id()
    
    # Generate random password
    password = generate_tenant_password()
    
    tenant = User(
        tenant_id=tenant_id,
        name=name,
        rent_amount=rent_amount,
        is_owner=False
    )
    tenant.set_password(password)
    
    # Add tenant to database first to get the user_id
    db.session.add(tenant)
    db.session.flush()  # This assigns the ID to the tenant object
    
    # Create initial electricity meter reading
    initial_electricity = MeterReading(
        user_id=tenant.id,
        reading_value=initial_electricity_reading,
        reading_date=datetime.now(),
        image_path='initial_reading.jpg',  # Placeholder image path
        is_processed=True,  # Mark as processed since it's entered by owner
        meter_type='electricity'
    )
    
    # Create initial water meter reading
    initial_water = MeterReading(
        user_id=tenant.id,
        reading_value=initial_water_reading,
        reading_date=datetime.now(),
        image_path='initial_reading.jpg',  # Placeholder image path
        is_processed=True,  # Mark as processed since it's entered by owner
        meter_type='water'
    )
    
    db.session.add(initial_electricity)
    db.session.add(initial_water)
    db.session.commit()
    
    return jsonify({
        'message': 'Tenant registered successfully',
        'tenant': {
            'id': tenant.id,
            'name': tenant.name,
            'tenant_id': tenant.tenant_id,
            'password': password  # Send the generated password
        }
    })

@app.route('/api/change_password', methods=['POST'])
@token_required
def change_password(current_user):
    if not request.is_json:
        return jsonify({'error': 'Missing JSON in request'}), 400
    
    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    
    if not all([current_password, new_password]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Verify current password
    if not current_user.check_password(current_password):
        return jsonify({'error': 'Current password is incorrect'}), 401
    
    # Update password
    current_user.set_password(new_password)
    db.session.commit()
    
    return jsonify({'message': 'Password updated successfully'})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000) 