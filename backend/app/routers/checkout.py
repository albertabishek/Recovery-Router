import re
import logging
import httpx
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import HTMLResponse
from app.config import settings
from app.services.payment_links import get_checkout_context

logger = logging.getLogger(__name__)

router = APIRouter(tags=["checkout"])

ORDER_ID_PATTERN = re.compile(r"^order_[A-Za-z0-9]{8,30}$")


@router.get("/pay/{order_id}", response_class=HTMLResponse)
async def checkout_page(
    order_id: str,
    t: str = Query(""),
):
    if not ORDER_ID_PATTERN.match(order_id):
        raise HTTPException(status_code=400, detail="Invalid order ID format")

    name = "Customer"
    email = ""
    phone = ""
    if t:
        ctx = get_checkout_context(t)
        if ctx:
            name = ctx.get("name", "Customer")
            email = ctx.get("email", "")
            phone = ctx.get("phone", "")

    """Hosted checkout page that opens Razorpay Standard Checkout for the given order."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Complete Your Payment</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
  }}
  .card {{
    background: white;
    border-radius: 16px;
    padding: 40px;
    max-width: 440px;
    width: 90%;
    text-align: center;
    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
  }}
  .logo {{ font-size: 48px; margin-bottom: 16px; }}
  h1 {{ font-size: 22px; color: #1a1a2e; margin-bottom: 8px; }}
  p {{ color: #666; margin-bottom: 24px; line-height: 1.5; }}
  .btn {{
    background: #528FF0;
    color: white;
    border: none;
    padding: 14px 32px;
    font-size: 16px;
    font-weight: 600;
    border-radius: 8px;
    cursor: pointer;
    width: 100%;
    transition: background 0.2s;
  }}
  .btn:hover {{ background: #3d7ce0; }}
  .secure {{ color: #999; font-size: 12px; margin-top: 16px; }}
  .spinner {{
    display: none;
    margin: 20px auto;
    width: 40px; height: 40px;
    border: 4px solid #eee;
    border-top: 4px solid #528FF0;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }}
  @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
  .loading .spinner {{ display: block; }}
  .loading .btn {{ display: none; }}
  .loading p {{ display: none; }}
</style>
</head>
<body>
<div class="card" id="card">
  <div class="logo">&#128179;</div>
  <h1>Complete Your Payment</h1>
  <p>Hi {_esc(name)}, click below to securely complete your payment via Razorpay.</p>
  <div class="spinner" id="spinner"></div>
  <button class="btn" onclick="openCheckout()">Pay Now</button>
  <p class="secure">&#128274; Secured by Razorpay</p>
</div>

<script src="https://checkout.razorpay.com/v1/checkout.js"></script>
<script>
  function openCheckout() {{
    document.getElementById('card').classList.add('loading');
    var options = {{
      key: '{settings.RAZORPAY_KEY_ID}',
      order_id: '{_esc_js(order_id)}',
      name: 'Recovery Router',
      description: 'Complete your payment',
      notes: {{
        source: 'recovery_router',
        recovery_order_id: '{_esc_js(order_id)}'
      }},
      prefill: {{
        name: '{_esc_js(name)}',
        email: '{_esc_js(email)}',
        contact: '{_esc_js(phone)}'
      }},
      theme: {{ color: '#528FF0' }},
      handler: function(response) {{
        document.getElementById('card').innerHTML =
          '<div class="logo">&#9989;</div>' +
          '<h1>Payment Successful!</h1>' +
          '<p style="display:block">Thank you, {_esc(name)}. Your payment has been received.</p>' +
          '<p class="secure" style="display:block">Payment ID: ' + response.razorpay_payment_id + '</p>';
      }},
      modal: {{
        ondismiss: function() {{
          document.getElementById('card').classList.remove('loading');
        }}
      }}
    }};
    var rzp = new Razorpay(options);
    rzp.on('payment.failed', function(response) {{
      document.getElementById('card').classList.remove('loading');
      alert('Payment failed: ' + response.error.description);
    }});
    rzp.open();
  }}
  // Auto-open checkout on page load
  setTimeout(openCheckout, 500);
</script>
</body>
</html>"""


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _esc_js(s: str) -> str:
    import json
    safe = json.dumps(str(s))[1:-1]
    return safe.replace("'", "\\'").replace("</", "<\\/")
