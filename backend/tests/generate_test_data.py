"""
Bulk test data generator for Recovery Router.
Generates 100+ diverse recovery events via the webhook API.
Run: python tests/generate_test_data.py
Requires: server running on http://127.0.0.1:8000
"""
import random
import time
import requests

BASE = "http://127.0.0.1:8000"

PAYMENT_METHODS = ["upi", "card", "netbanking", "wallet"]
CURRENCIES = ["INR"]

PAYMENT_FAILURE_SCENARIOS = [
    ("TIMEOUT", "UPI payment timed out after 5 minutes", "upi"),
    ("BANK_DOWNTIME", "Bank server temporarily unavailable", "netbanking"),
    ("CARD_EXPIRED", "Card has expired", "card"),
    ("INSUFFICIENT_FUNDS", "Insufficient funds in account", "card"),
    ("GATEWAY_ERROR", "Payment gateway technical error", "upi"),
    ("NETWORK_ERROR", "Network connectivity issue during payment", "netbanking"),
    ("UPI_PIN_ERROR", "Incorrect UPI PIN entered", "upi"),
    ("CARD_DECLINED", "Card declined by issuing bank", "card"),
]

NAMES = [
    "Rahul Sharma", "Priya Patel", "Amit Kumar", "Sneha Gupta", "Vikram Singh",
    "Anita Desai", "Rohan Mehta", "Kavita Nair", "Suresh Reddy", "Deepa Iyer",
    "Arjun Kapoor", "Meera Joshi", "Karthik Rao", "Pooja Verma", "Nikhil Bansal",
    "Swati Mishra", "Rajesh Pillai", "Divya Menon", "Sanjay Tiwari", "Ritu Agarwal",
    "Arun Prasad", "Lakshmi Devi", "Manish Saxena", "Sunita Bhat", "Vivek Chauhan",
    "Neha Srinivasan", "Prakash Goel", "Anjali Dubey", "Gaurav Malhotra", "Padma Rao",
]

DOMAINS = ["gmail.com", "yahoo.co.in", "outlook.com", "hotmail.com", "rediffmail.com"]

SENT = 0
FAILED = 0


def random_email(name):
    clean = name.lower().replace(" ", ".").replace("'", "")
    return f"{clean}{random.randint(1, 999)}@{random.choice(DOMAINS)}"


def random_phone():
    return f"+91{random.randint(7000000000, 9999999999)}"


def send_event(body, label=""):
    global SENT, FAILED
    try:
        r = requests.post(f"{BASE}/webhook/recovery-router", json=body, timeout=15)
        if r.status_code == 200 and r.json().get("status") == "accepted":
            SENT += 1
            return True
        elif r.json().get("status") == "duplicate":
            SENT += 1
            return True
        else:
            FAILED += 1
            print(f"  WARN: {label} -> {r.status_code}: {r.text[:100]}")
            return False
    except Exception as e:
        FAILED += 1
        print(f"  ERROR: {label} -> {e}")
        return False


def generate_payment_failures(count=50):
    print(f"\n[1/3] Generating {count} payment failures...")
    for i in range(count):
        error_code, error_desc, method = random.choice(PAYMENT_FAILURE_SCENARIOS)
        name = random.choice(NAMES)
        amount = random.choice([199, 499, 799, 999, 1499, 1999, 2499, 2999, 3999, 4999, 5999, 7999, 9999, 14999, 24999])

        body = {
            "event_type": "payment_failure",
            "payment_id": f"pay_BULK_{int(time.time()*1000)}_{i}",
            "order_id": f"order_BULK_{int(time.time()*1000)}_{i}",
            "amount": amount,
            "currency": "INR",
            "method": method,
            "error_code": error_code,
            "error_description": error_desc,
            "customer_email": random_email(name),
            "customer_phone": random_phone(),
            "customer_name": name,
        }
        send_event(body, f"payment_failure #{i+1}")

        if (i + 1) % 10 == 0:
            print(f"  Sent {i+1}/{count} payment failures")
        time.sleep(0.1)


def generate_cart_abandonments(count=30):
    print(f"\n[2/3] Generating {count} cart abandonments...")
    for i in range(count):
        name = random.choice(NAMES)
        high_value = random.random() > 0.4
        cart_value = random.choice([2999, 4999, 5999, 7999, 9999, 14999]) if high_value else random.choice([49, 99, 149, 199])
        items = random.randint(1, 10) if high_value else random.randint(1, 2)

        body = {
            "event_type": "cart_abandonment",
            "payment_id": f"pay_CART_BULK_{int(time.time()*1000)}_{i}",
            "amount": 0,
            "cart_value": cart_value,
            "items_in_cart": items,
            "currency": "INR",
            "customer_email": random_email(name),
            "customer_phone": random_phone(),
            "customer_name": name,
        }
        send_event(body, f"cart_abandonment #{i+1}")

        if (i + 1) % 10 == 0:
            print(f"  Sent {i+1}/{count} cart abandonments")
        time.sleep(0.1)


def generate_overdue_invoices(count=20):
    print(f"\n[3/3] Generating {count} overdue invoices...")
    for i in range(count):
        name = random.choice(NAMES)
        days = random.choice([1, 2, 3, 5, 7, 10, 14, 21, 30, 45, 60, 90])
        amount = random.choice([5000, 10000, 15000, 25000, 50000, 75000, 100000])

        body = {
            "event_type": "invoice_overdue",
            "invoice_id": f"inv_BULK_{int(time.time()*1000)}_{i}",
            "amount": amount,
            "currency": "INR",
            "days_overdue": days,
            "customer_email": random_email(name),
            "customer_phone": random_phone(),
            "customer_name": name,
        }
        send_event(body, f"invoice_overdue #{i+1}")

        if (i + 1) % 10 == 0:
            print(f"  Sent {i+1}/{count} overdue invoices")
        time.sleep(0.1)


def print_analytics():
    print("\n[Stats] Fetching analytics after data generation...")
    try:
        r = requests.get(f"{BASE}/api/analytics", timeout=30)
        if r.status_code == 200:
            data = r.json()
            s = data["summary"]
            print(f"  Total events:     {s['total_events']}")
            print(f"  Recovered:        {s['recovered_count']}")
            print(f"  Pending:          {s['pending_count']}")
            print(f"  Exhausted:        {s['exhausted_count']}")
            print(f"  No action:        {s['no_action_count']}")
            print(f"  Recovery rate:    {s['recovery_rate_percent']}%")
            print(f"  Total amount:     INR {s['total_amount']:,.2f}")
            print(f"  Recovered amount: INR {s['recovered_amount']:,.2f}")

            lift = data["ai_lift"]
            print(f"\n  AI Lift:")
            print(f"    Baseline rate:      {lift['baseline_rate_percent']}%")
            print(f"    AI recovery rate:   {lift['ai_recovery_rate_percent']}%")
            print(f"    Improvement:        {lift['improvement_points']} pts")
            print(f"    Additional revenue: INR {lift['additional_revenue_recovered']:,.2f}")

            if data.get("by_event_type"):
                print(f"\n  By event type:")
                for et, stats in data["by_event_type"].items():
                    print(f"    {et}: {stats['total']} events, {stats['recovery_rate']}% recovered")

            if data.get("channel_ranking"):
                print(f"\n  Channel ranking:")
                for ch in data["channel_ranking"]:
                    print(f"    {ch['channel']}: {ch['total']} events, {ch['recovery_rate']}% recovered")
        else:
            print(f"  Analytics failed: {r.status_code}")
    except Exception as e:
        print(f"  Analytics error: {e}")


def main():
    print("=" * 60)
    print("  RECOVERY ROUTER — BULK TEST DATA GENERATOR")
    print("=" * 60)

    # Check server is up
    try:
        r = requests.get(f"{BASE}/", timeout=5)
        assert r.status_code == 200
    except Exception:
        print("ERROR: Server not running at http://127.0.0.1:8000")
        print("Start it first: python -m uvicorn app.main:app --host 127.0.0.1 --port 8000")
        return

    generate_payment_failures(50)
    generate_cart_abandonments(30)
    generate_overdue_invoices(20)

    print("\n" + "=" * 60)
    print(f"  DONE: {SENT} sent, {FAILED} failed out of {SENT + FAILED}")
    print("=" * 60)

    time.sleep(3)
    print_analytics()


if __name__ == "__main__":
    main()
