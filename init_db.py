from app import app, db
from models import User, ElectricityRate
from datetime import datetime

def init_database():
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Set initial electricity rate only
        rate = ElectricityRate.query.first()
        if not rate:
            initial_rate = ElectricityRate(
                rate_per_unit=0.12,  # Change this to your local electricity rate
                effective_from=datetime.now()
            )
            db.session.add(initial_rate)
            db.session.commit()
            print("Added initial electricity rate")
        else:
            print("Database already initialized")

if __name__ == '__main__':
    init_database() 