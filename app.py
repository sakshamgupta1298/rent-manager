from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from models import db, User, MeterReading, Payment, ElectricityRate, WaterBill
from datetime import datetime
import os
from dotenv import load_dotenv
import stripe
from PIL import Image

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///rentmanager.db')
app.config['UPLOAD_FOLDER'] = 'static/uploads'
stripe.api_key = os.getenv('STRIPE_API_KEY')

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.is_owner:
            return redirect(url_for('owner_dashboard'))
        return redirect(url_for('tenant_dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        tenant_id = request.form.get('tenant_id')
        password = request.form.get('password')
        
        # Add debug prints
        print(f"Attempting login with tenant_id/email: {tenant_id}")
        
        # Try to find user by tenant_id first (for tenants)
        user = User.query.filter_by(tenant_id=tenant_id).first()
        if not user:
            # If not found, try email (for owner)
            user = User.query.filter_by(email=tenant_id).first()
            print(f"Found user by email: {user.email if user else 'None'}")
        else:
            print(f"Found user by tenant_id: {user.tenant_id}")
        
        if user and user.check_password(password):
            login_user(user)
            print(f"Successfully logged in user: {user.email}")
            return redirect(url_for('index'))
        
        print("Invalid login credentials")
        flash('Invalid credentials. Please check your email/tenant ID and password.')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        name = request.form.get('name')
        password = request.form.get('password')
        
        # Add debug prints
        print(f"Attempting to register new owner with email: {email}")
        
        # Check if any owner exists
        existing_owner = User.query.filter_by(is_owner=True).first()
        if existing_owner:
            print(f"Found existing owner with email: {existing_owner.email}")
            flash('An owner account already exists. Please login instead.')
            return redirect(url_for('login'))
        
        # Check for existing email
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            print(f"Email {email} already registered")
            flash('Email already registered')
            return redirect(url_for('register'))
        
        # Create new owner user
        user = User(
            email=email,
            name=name,
            is_owner=True,
            rent_amount=0.0  # Not relevant for owner
        )
        user.set_password(password)
        
        try:
            print("Adding new owner to database")
            db.session.add(user)
            db.session.commit()
            print(f"Successfully registered owner with email: {email}")
            flash('Registration successful! Please login.')
            return redirect(url_for('login'))
        except Exception as e:
            print(f"Error during registration: {str(e)}")
            db.session.rollback()
            flash('An error occurred during registration. Please try again.')
            return redirect(url_for('register'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/tenant_dashboard')
@login_required
def tenant_dashboard():
    if current_user.is_owner:
        return redirect(url_for('owner_dashboard'))
    
    # Get the latest reading
    latest_reading = MeterReading.query.filter_by(user_id=current_user.id).order_by(MeterReading.reading_date.desc()).first()
    previous_reading = None
    if latest_reading:
        previous_reading = MeterReading.query.filter(
            MeterReading.user_id == current_user.id,
            MeterReading.reading_date < latest_reading.reading_date
        ).order_by(MeterReading.reading_date.desc()).first()
    
    # Check for existing payment for current billing period
    existing_payment = None
    if latest_reading:
        existing_payment = Payment.query.filter(
            Payment.user_id == current_user.id,
            Payment.payment_date >= latest_reading.reading_date
        ).order_by(Payment.payment_date.desc()).first()
    
    # Determine if payment options should be shown
    show_payment_options = True
    if existing_payment and existing_payment.status in ['pending', 'completed', 'confirmed']:
        show_payment_options = False
    
    # Get last 10 meter readings
    meter_readings = MeterReading.query.filter_by(user_id=current_user.id).order_by(MeterReading.reading_date.desc()).limit(10).all()
    
    # Calculate consumption for each reading
    for reading in meter_readings:
        reading.previous = MeterReading.query.filter(
            MeterReading.user_id == current_user.id,
            MeterReading.reading_date < reading.reading_date
        ).order_by(MeterReading.reading_date.desc()).first()
        
        if reading.previous:
            reading.consumption = reading.reading_value - reading.previous.reading_value
        else:
            reading.consumption = 0
    
    current_rate = ElectricityRate.query.order_by(ElectricityRate.effective_from.desc()).first()
    
    # Get payment history
    payments = Payment.query.filter_by(user_id=current_user.id).order_by(Payment.payment_date.desc()).limit(10).all()
    
    # Get latest electricity reading
    latest_electricity_reading = MeterReading.query.filter_by(
        user_id=current_user.id,
        meter_type='electricity'
    ).order_by(MeterReading.reading_date.desc()).first()
    
    if latest_electricity_reading:
        latest_electricity_reading.previous = MeterReading.query.filter(
            MeterReading.user_id == current_user.id,
            MeterReading.meter_type == 'electricity',
            MeterReading.reading_date < latest_electricity_reading.reading_date
        ).order_by(MeterReading.reading_date.desc()).first()
    
    # Get latest water reading and bill
    latest_water_reading = MeterReading.query.filter_by(
        user_id=current_user.id,
        meter_type='water'
    ).order_by(MeterReading.reading_date.desc()).first()
    
    if latest_water_reading:
        latest_water_reading.previous = MeterReading.query.filter(
            MeterReading.user_id == current_user.id,
            MeterReading.meter_type == 'water',
            MeterReading.reading_date < latest_water_reading.reading_date
        ).order_by(MeterReading.reading_date.desc()).first()
    
    # Get total number of tenants
    total_tenant = User.query.filter_by(is_owner=False).count()
    
    water_bill = WaterBill.query.order_by(WaterBill.billing_date.desc()).first()
    
    return render_template('tenant_dashboard.html',
                         latest_reading=latest_reading,
                         previous_reading=previous_reading,
                         meter_readings=meter_readings,
                         current_rate=current_rate,
                         payments=payments,
                         existing_payment=existing_payment,
                         show_payment_options=show_payment_options,
                         latest_electricity_reading=latest_electricity_reading,
                         latest_water_reading=latest_water_reading,
                         water_bill=water_bill,
                         total_tenant=total_tenant)

@app.route('/owner_dashboard')
@login_required
def owner_dashboard():
    if not current_user.is_owner:
        return redirect(url_for('tenant_dashboard'))
    
    # Get all tenants
    tenants = User.query.filter_by(is_owner=False).all()
    
    # Get all readings ordered by date
    readings = MeterReading.query.join(User).filter(User.is_owner == False).order_by(MeterReading.reading_date.desc()).limit(50).all()
    
    # Create a dictionary to store readings by tenant and type
    tenant_readings = {}
    
    # Process all readings into the dictionary
    for tenant in tenants:
        tenant_readings[tenant.id] = {
            'electricity': {'current': None, 'previous': None},
            'water': {'current': None, 'previous': None}
        }
        
        # Get the latest electricity reading
        latest_electricity = MeterReading.query.filter_by(
            user_id=tenant.id,
            meter_type='electricity'
        ).order_by(MeterReading.reading_date.desc()).first()
        
        if latest_electricity:
            tenant_readings[tenant.id]['electricity']['current'] = latest_electricity
            
            # Get previous electricity reading
            previous_electricity = MeterReading.query.filter(
                MeterReading.user_id == tenant.id,
                MeterReading.meter_type == 'electricity',
                MeterReading.reading_date < latest_electricity.reading_date
            ).order_by(MeterReading.reading_date.desc()).first()
            
            tenant_readings[tenant.id]['electricity']['previous'] = previous_electricity
        
        # Get the latest water reading
        latest_water = MeterReading.query.filter_by(
            user_id=tenant.id,
            meter_type='water'
        ).order_by(MeterReading.reading_date.desc()).first()
        
        if latest_water:
            tenant_readings[tenant.id]['water']['current'] = latest_water
            
            # Get previous water reading
            previous_water = MeterReading.query.filter(
                MeterReading.user_id == tenant.id,
                MeterReading.meter_type == 'water',
                MeterReading.reading_date < latest_water.reading_date
            ).order_by(MeterReading.reading_date.desc()).first()
            
            tenant_readings[tenant.id]['water']['previous'] = previous_water
    
    # For each reading, get its previous reading for consumption calculation
    for reading in readings:
        reading.previous_reading = MeterReading.query.filter(
            MeterReading.user_id == reading.user_id,
            MeterReading.meter_type == reading.meter_type,
            MeterReading.reading_date < reading.reading_date
        ).order_by(MeterReading.reading_date.desc()).first()
    
    # Get current electricity rate
    current_rate = ElectricityRate.query.order_by(ElectricityRate.effective_from.desc()).first()
    
    # Get latest water bill
    water_bill = WaterBill.query.order_by(WaterBill.billing_date.desc()).first()
    
    # Fetch all payments
    payments = (Payment.query
                .join(User)
                .order_by(Payment.payment_date.desc())
                .all())
    
    # Update this section to correctly fetch all pending payments
    pending_payments = Payment.query.filter_by(status='pending').order_by(Payment.payment_date.desc()).all()

    return render_template('owner_dashboard.html',
                         tenants=tenants,
                         readings=readings,
                         tenant_readings=tenant_readings,
                         current_rate=current_rate,
                         water_bill=water_bill,
                         pending_payments=pending_payments,
                         payments=payments)

@app.route('/register_tenant', methods=['GET', 'POST'])
@login_required
def register_tenant():
    if not current_user.is_owner:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if request.method == 'POST':
        name = request.form.get('name')
        rent_amount = float(request.form.get('rent_amount'))
        initial_electricity_reading = float(request.form.get('initial_electricity_reading'))
        initial_water_reading = float(request.form.get('initial_water_reading'))
        
        # Generate unique tenant ID and password
        tenant_id = User.generate_unique_tenant_id()
        password = User.generate_tenant_password()
        
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
        
        flash(f'Tenant registered successfully! Tenant ID: {tenant_id}, Password: {password}')
        return redirect(url_for('owner_dashboard'))
    
    return render_template('register_tenant.html')

@app.route('/set_electricity_rate', methods=['POST'])
@login_required
def set_electricity_rate():
    if not current_user.is_owner:
        return jsonify({'error': 'Unauthorized'}), 403
    
    rate = float(request.form.get('rate_per_unit'))
    
    new_rate = ElectricityRate(
        rate_per_unit=rate,
        effective_from=datetime.now()
    )
    db.session.add(new_rate)
    db.session.commit()
    
    flash('Electricity rate updated successfully')
    return redirect(url_for('owner_dashboard'))

@app.route('/upload_reading', methods=['POST'])
@login_required
def upload_reading():
    if current_user.is_owner:
        return redirect(url_for('owner_dashboard'))
    
    # Handle electricity reading
    if 'electricity_reading' in request.form and 'electricity_image' in request.files:
        electricity_reading = float(request.form.get('electricity_reading'))
        electricity_image = request.files['electricity_image']
        
        if electricity_image.filename:
            filename = secure_filename(f"electricity_{current_user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{electricity_image.filename}")
            electricity_image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        else:
            filename = None
        
        reading = MeterReading(
            user_id=current_user.id,
            reading_value=electricity_reading,
            reading_date=datetime.now(),
            image_path=filename,
            meter_type='electricity',
            is_processed=True
        )
        db.session.add(reading)
    
    # Handle water reading
    if 'water_reading' in request.form and 'water_image' in request.files:
        water_reading = float(request.form.get('water_reading'))
        water_image = request.files['water_image']
        
        if water_image.filename:
            filename = secure_filename(f"water_{current_user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{water_image.filename}")
            water_image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        else:
            filename = None
        
        reading = MeterReading(
            user_id=current_user.id,
            reading_value=water_reading,
            reading_date=datetime.now(),
            image_path=filename,
            meter_type='water',
            is_processed=True
        )
        db.session.add(reading)
        
        # Calculate water bill
        total_tenants = User.query.filter_by(is_owner=False).count()
        initial_water_reading = MeterReading.query.filter_by(
            meter_type='water'
        ).order_by(MeterReading.reading_date).first()
        
        if initial_water_reading and initial_water_reading.reading_value < water_reading:
            total_usage = water_reading - initial_water_reading.reading_value
            # Get current electricity rate
            current_rate = ElectricityRate.query.order_by(ElectricityRate.effective_from.desc()).first()
            if current_rate:
                amount_per_tenant = (total_usage / (total_tenants + 1)) * current_rate.rate_per_unit
            else:
                amount_per_tenant = total_usage / (total_tenants + 1)
            
            water_bill = WaterBill(
                total_amount=total_usage,
                billing_date=datetime.now(),
                total_tenants=total_tenants,
                amount_per_tenant=amount_per_tenant
            )
            db.session.add(water_bill)
    
    db.session.commit()
    flash('Readings uploaded successfully')
    return redirect(url_for('tenant_dashboard'))

@app.route('/create_payment', methods=['POST'])
@login_required
def create_payment():
    payment_method = request.json.get('payment_method', 'card')
    if payment_method not in ['card', 'cash', 'bank_transfer']:
        return jsonify({'error': 'Invalid payment method'}), 400

    # Get latest electricity reading and calculate electricity bill
    latest_electricity_reading = MeterReading.query.filter_by(
        user_id=current_user.id, 
        meter_type='electricity'
    ).order_by(MeterReading.reading_date.desc()).first()
    
    electricity_cost = 0
    if latest_electricity_reading:
        previous_electricity_reading = MeterReading.query.filter(
            MeterReading.user_id == current_user.id,
            MeterReading.meter_type == 'electricity',
            MeterReading.reading_date < latest_electricity_reading.reading_date
        ).order_by(MeterReading.reading_date.desc()).first()
        
        if previous_electricity_reading:
            current_rate = ElectricityRate.query.order_by(ElectricityRate.effective_from.desc()).first()
            if current_rate:
                units_consumed = latest_electricity_reading.reading_value - previous_electricity_reading.reading_value
                electricity_cost = units_consumed * current_rate.rate_per_unit
    
    # Get water bill amount
    water_bill = WaterBill.query.order_by(WaterBill.billing_date.desc()).first()
    water_cost = water_bill.amount_per_tenant if water_bill else 0
    
    # Calculate total amount
    total_amount = current_user.rent_amount + electricity_cost + water_cost
    
    # Create payment record
    payment = Payment(
        user_id=current_user.id,
        amount=total_amount,
        rent_component=current_user.rent_amount,
        electricity_component=electricity_cost,
        water_component=water_cost,
        payment_date=datetime.now(),
        payment_method=payment_method,
        status='pending'  # Make sure this is set to 'pending' for all methods
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
        # For cash and UPI payments
        reference = f"RENT{datetime.now().strftime('%Y%m%d%H%M%S')}{current_user.id}"
        payment.transaction_reference = reference
        db.session.add(payment)
        db.session.commit()
        
        return jsonify({
            'reference': reference,
            'amount': total_amount,
            'message': f'Please use reference {reference} when making the payment'
        })

@app.route('/confirm_payment/<int:payment_id>', methods=['POST'])
@login_required
def confirm_payment(payment_id):
    if not current_user.is_owner:
        return jsonify({'error': 'Unauthorized'}), 403
    
    payment = Payment.query.get_or_404(payment_id)
    payment.status = 'confirmed'
    db.session.commit()
    
    # After successful confirmation, redirect back to owner dashboard
    return redirect(url_for('owner_dashboard'))

@app.route('/reject_payment/<int:payment_id>', methods=['POST'])
@login_required
def reject_payment(payment_id):
    if not current_user.is_owner:
        return jsonify({'error': 'Unauthorized'}), 403
    
    payment = Payment.query.get_or_404(payment_id)
    payment.status = 'rejected'
    db.session.commit()
    
    # After successful rejection, redirect back to owner dashboard
    return redirect(url_for('owner_dashboard'))

@app.route('/payment_success')
@login_required
def payment_success():
    payment_intent_id = request.args.get('payment_intent')
    if payment_intent_id:
        payment = Payment.query.filter_by(stripe_payment_id=payment_intent_id).first()
        if payment:
            payment.status = 'completed'
            db.session.commit()
            flash('Payment successful!')
    return redirect(url_for('tenant_dashboard'))

@app.route('/delete_tenant/<int:tenant_id>', methods=['POST'])
@login_required
def delete_tenant(tenant_id):
    if not current_user.is_owner:
        return jsonify({'error': 'Unauthorized'}), 403
    
    tenant = User.query.get(tenant_id)
    if not tenant:
        flash('Tenant not found')
        return redirect(url_for('owner_dashboard'))
    
    if tenant.is_owner:
        flash('Cannot delete owner account')
        return redirect(url_for('owner_dashboard'))
    
    # Delete associated meter readings
    MeterReading.query.filter_by(user_id=tenant.id).delete()
    
    # Delete associated payments
    Payment.query.filter_by(user_id=tenant.id).delete()
    
    # Delete tenant
    db.session.delete(tenant)
    db.session.commit()
    
    flash(f'Tenant {tenant.name} has been deleted')
    return redirect(url_for('owner_dashboard'))

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Validate current password
        if not current_user.check_password(current_password):
            flash('Current password is incorrect')
            return redirect(url_for('change_password'))
        
        # Validate new password
        if new_password != confirm_password:
            flash('New passwords do not match')
            return redirect(url_for('change_password'))
        
        if len(new_password) < 8:
            flash('New password must be at least 8 characters long')
            return redirect(url_for('change_password'))
        
        # Update password
        current_user.set_password(new_password)
        db.session.commit()
        
        flash('Password updated successfully')
        return redirect(url_for('tenant_dashboard'))
    
    return render_template('change_password.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # For local development
    app.run(debug=True, host='0.0.0.0', port=5000)
    
    # For production deployment, uncomment the following:
    # from waitress import serve
    # serve(app, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))