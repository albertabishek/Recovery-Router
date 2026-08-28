"""
Generate 100 events and process them synchronously (bypassing Celery queue).
This directly calls process_recovery_event() to populate the DB.
"""
import sys
import random
import time
import logging

sys.path.insert(0, r"C:\Users\ELCOT\Desktop\Razorpay_buildathon\backend")

logging.basicConfig(level=logging.WARNING)

from app.tasks.recovery import process_recovery_event
from app.database import get_supabase

PAYMENT_SCENARIOS = [
    ("TIMEOUT", "UPI payment timed out", "upi"),
    ("BANK_DOWNTIME", "Bank server temporarily unavailable", "netbanking"),
    ("CARD_EXPIRED", "Card has expired", "card"),
    ("INSUFFICIENT_FUNDS", "Insufficient funds", "card"),
    ("GATEWAY_ERROR", "Payment gateway error", "upi"),
    ("NETWORK_ERROR", "Network connectivity issue", "netbanking"),
    ("UPI_PIN_ERROR", "Incorrect UPI PIN", "upi"),
    ("CARD_DECLINED", "Card declined by bank", "card"),
]

NAMES = [
    "Rahul Sharma", "Priya Patel", "Amit Kumar", "Sneha Gupta", "Vikram Singh",
    "Anita Desai", "Rohan Mehta", "Kavita Nair", "Suresh Reddy", "Deepa Iyer",
    "Arjun Kapoor", "Meera Joshi", "Karthik Rao", "Pooja Verma", "Nikhil Bansal",
    "Swati Mishra", "Rajesh Pillai", "Divya Menon", "Sanjay Tiwari", "Ritu Agarwal",
    "Arun Prasad", "Lakshmi Devi", "Manish Saxena", "Sunita Bhat", "Vivek Chauhan",
]

processed = 0
failed = 0


def gen_email(name):
    return f"{name.lower().replace(' ', '.')}{random.randint(1,999)}@testmail.com"


def gen_phone():
    return f"+91{random.randint(7000000000, 9999999999)}"


def process_one(event_data, label):
    global processed, failed
    try:
        result = process_recovery_event(event_data)
        processed += 1
        return result
    except Exception as e:
        failed += 1
        if failed <= 3:
            print(f"  Error on {label}: {e}")
        return None


print("=" * 60)
print("  DIRECT EVENT PROCESSING (bypassing Celery queue)")
print("=" * 60)

# Get current count
sb = get_supabase()
before = sb.table("recovery_events").select("id", count="exact").execute()
print(f"Events before: {before.count}")

# 1. Payment failures (60)
print("\n[1/3] Processing 60 payment failures...")
for i in range(60):
    error_code, error_desc, method = random.choice(PAYMENT_SCENARIOS)
    name = random.choice(NAMES)
    amount = random.choice([199, 499, 799, 999, 1499, 1999, 2499, 2999, 3999, 4999, 7999, 9999, 14999])

    event_data = {
        "event_type": "payment_failure",
        "payment_id": f"pay_DIRECT_{int(time.time()*1000)}_{i}",
        "order_id": f"order_DIRECT_{int(time.time()*1000)}_{i}",
        "amount": amount,
        "currency": "INR",
        "method": method,
        "error_code": error_code,
        "error_description": error_desc,
        "customer_email": gen_email(name),
        "customer_phone": gen_phone(),
        "customer_name": name,
        "source": "bulk_test",
    }
    process_one(event_data, f"pf#{i+1}")
    if (i + 1) % 20 == 0:
        print(f"  {i+1}/60 done")

# 2. Cart abandonments (25)
print("\n[2/3] Processing 25 cart abandonments...")
for i in range(25):
    name = random.choice(NAMES)
    high = random.random() > 0.4
    cart_value = random.choice([2999, 4999, 5999, 7999, 9999, 14999]) if high else random.choice([49, 99, 149, 199])
    items = random.randint(1, 10) if high else random.randint(1, 2)

    event_data = {
        "event_type": "cart_abandonment",
        "payment_id": f"pay_CART_D_{int(time.time()*1000)}_{i}",
        "amount": cart_value,
        "cart_value": cart_value,
        "items_in_cart": items,
        "currency": "INR",
        "customer_email": gen_email(name),
        "customer_phone": gen_phone(),
        "customer_name": name,
        "source": "bulk_test",
    }
    process_one(event_data, f"cart#{i+1}")
    if (i + 1) % 10 == 0:
        print(f"  {i+1}/25 done")

# 3. Overdue invoices (15)
print("\n[3/3] Processing 15 overdue invoices...")
for i in range(15):
    name = random.choice(NAMES)
    days = random.choice([1, 2, 3, 5, 7, 10, 14, 21, 30, 45, 60, 90])
    amount = random.choice([5000, 10000, 15000, 25000, 50000, 75000, 100000])

    event_data = {
        "event_type": "invoice_overdue",
        "invoice_id": f"inv_D_{int(time.time()*1000)}_{i}",
        "amount": amount,
        "currency": "INR",
        "days_overdue": days,
        "customer_email": gen_email(name),
        "customer_phone": gen_phone(),
        "customer_name": name,
        "source": "bulk_test",
    }
    process_one(event_data, f"inv#{i+1}")
    if (i + 1) % 10 == 0:
        print(f"  {i+1}/15 done")

# Final stats
after = sb.table("recovery_events").select("id", count="exact").execute()
print(f"\n{'=' * 60}")
print(f"  DONE: {processed} processed, {failed} failed")
print(f"  Events before: {before.count}, after: {after.count} (+{after.count - before.count})")
print(f"{'=' * 60}")
