# DwellSync

A web application for managing rental properties, tracking utility bills, and handling tenant payments.

## Features

- **Owner Dashboard**: Manage properties, tenants, and view payment history
- **Tenant Dashboard**: View bills, make payments, and upload meter readings
- **Payment System**: Support for multiple payment methods (card, bank transfer, cash)
- **Utility Tracking**: Monitor electricity and water consumption
- **Billing System**: Automatically calculate bills based on meter readings
- **Image Upload**: Allow tenants to upload photos of meter readings

## Technology Stack

- **Backend**: Flask (Python)
- **Database**: SQLAlchemy (SQLite)
- **Frontend**: HTML, CSS, JavaScript, Bootstrap
- **Payment Gateway**: Stripe API

## Setup and Installation

1. Clone the repository
```
git clone <repository-url>
```

2. Create a virtual environment and activate it
```
python -m venv venv
venv\Scripts\activate  # On Windows
source venv/bin/activate  # On Unix/MacOS
```

3. Install dependencies
```
pip install -r requirements.txt
```

4. Set up environment variables
Create a `.env` file with the following variables:
```
SECRET_KEY=your_secret_key
STRIPE_API_KEY=your_stripe_api_key
DATABASE_URL=sqlite:///rentmanager.db
```

5. Initialize the database
```
python init_db.py
```

6. Run the application
```
python app.py
```

7. Access the application at http://localhost:5000

## License

This project is licensed under the MIT License 