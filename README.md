# Rent Management System

A Python-based web application for managing rent payments, utility readings, and tenant communications.

## Features

- Tenant registration and management
- Monthly rent payment reminders
- Electricity meter reading uploads
- Automated billing calculation
- Secure payment processing
- Owner dashboard for tenant management

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables in `.env`:
```
DATABASE_URL=sqlite:///rentmanager.db
SECRET_KEY=your-secret-key
STRIPE_API_KEY=your-stripe-api-key
```

4. Initialize the database:
```bash
python init_db.py
```

5. Run the application:
```bash
python app.py
```

## Usage

1. Owner can register and manage tenants through the admin dashboard
2. Tenants can:
   - Upload electricity meter readings
   - View bills and payment history
   - Make payments through the platform
   - Receive automated payment reminders

## Security

- Password hashing using werkzeug
- Secure file uploads
- Protected routes using Flask-Login
- CSRF protection 