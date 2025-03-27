from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from models import User, db
import requests

def send_sms_notification(phone_number, message):
    # Integrate with SMS service provider (e.g., Twilio)
    # Implementation depends on your chosen SMS service
    pass

def check_and_send_reminders():
    today = datetime.now().day
    tenants = User.query.filter(
        User.is_owner == False,
        User.rent_due_day == today
    ).all()
    
    for tenant in tenants:
        message = (
            f"Hi {tenant.name}, this is a reminder that your rent payment of "
            f"₹{tenant.rent_amount:.2f} is due today. Please make the payment "
            f"through your tenant dashboard."
        )
        if tenant.phone_number:
            send_sms_notification(tenant.phone_number, message)

def init_scheduler():
    scheduler = BackgroundScheduler()
    # Run every day at 9:00 AM
    scheduler.add_job(
        check_and_send_reminders,
        CronTrigger(hour=9, minute=0)
    )
    scheduler.start() 