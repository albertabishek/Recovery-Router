from html import escape as _h


def _safe_url(url: str) -> str:
    if url and url.startswith(("http://", "https://")):
        return _h(url, quote=True)
    return "#"


def recovery_email_html(
    customer_name: str,
    amount: float,
    currency: str,
    failure_category: str,
    payment_link_url: str,
    reasoning: str,
) -> str:
    name = _h(customer_name)
    cur = _h(currency)
    link = _safe_url(payment_link_url)
    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: #1a1a2e; padding: 24px; border-radius: 12px 12px 0 0;">
            <h1 style="color: #fff; margin: 0; font-size: 20px;">Recovery Router</h1>
            <p style="color: #a0a0b0; margin: 4px 0 0 0; font-size: 13px;">Intelligent Payment Recovery</p>
        </div>
        <div style="background: #fff; padding: 32px; border: 1px solid #e0e0e0;">
            <p style="font-size: 16px; color: #333;">Hi {name},</p>
            <p style="font-size: 15px; color: #555; line-height: 1.6;">
                We noticed your payment of <strong>{cur} {amount:,.2f}</strong> didn't go through.
                Don't worry — these things happen, and we've made it easy to complete your payment.
            </p>
            <div style="text-align: center; margin: 32px 0;">
                <a href="{link}"
                   style="background: #2563eb; color: #fff; padding: 14px 32px; border-radius: 8px;
                          text-decoration: none; font-size: 16px; font-weight: 600; display: inline-block;">
                    Complete Payment
                </a>
            </div>
            <p style="font-size: 13px; color: #888; line-height: 1.5;">
                This link will expire within your recovery window. If you've already completed this payment, please ignore this email.
            </p>
        </div>
        <div style="background: #f8f9fa; padding: 16px 32px; border-radius: 0 0 12px 12px; border: 1px solid #e0e0e0; border-top: none;">
            <p style="font-size: 12px; color: #999; margin: 0;">
                Powered by Recovery Router — Razorpay AI Buildathon
            </p>
        </div>
    </div>
    """


def recovery_whatsapp_message(
    customer_name: str,
    amount: float,
    currency: str,
    payment_link_url: str,
) -> str:
    return (
        f"Hi {customer_name}, your payment of {currency} {amount:,.2f} "
        f"didn't go through. Complete it here: {payment_link_url}"
    )


def recovery_sms_message(amount: float, currency: str, payment_link_url: str) -> str:
    return f"Payment of {currency} {amount:,.0f} failed. Retry: {payment_link_url}"


def escalation_email_html(
    customer_name: str,
    amount: float,
    currency: str,
    attempt_number: int,
    payment_link_url: str,
) -> str:
    if attempt_number <= 1:
        tone = "friendly reminder"
    elif attempt_number == 2:
        tone = "follow-up"
    elif attempt_number == 3:
        tone = "urgent notice"
    else:
        tone = "final notice"

    name = _h(customer_name)
    cur = _h(currency)
    link = _safe_url(payment_link_url)
    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: #1a1a2e; padding: 24px; border-radius: 12px 12px 0 0;">
            <h1 style="color: #fff; margin: 0; font-size: 20px;">Recovery Router</h1>
        </div>
        <div style="background: #fff; padding: 32px; border: 1px solid #e0e0e0;">
            <p style="font-size: 16px; color: #333;">Hi {name},</p>
            <p style="font-size: 15px; color: #555; line-height: 1.6;">
                This is a {tone} about your pending payment of
                <strong>{cur} {amount:,.2f}</strong>.
            </p>
            <div style="text-align: center; margin: 32px 0;">
                <a href="{link}"
                   style="background: #2563eb; color: #fff; padding: 14px 32px; border-radius: 8px;
                          text-decoration: none; font-size: 16px; font-weight: 600; display: inline-block;">
                    Complete Payment Now
                </a>
            </div>
        </div>
        <div style="background: #f8f9fa; padding: 16px 32px; border-radius: 0 0 12px 12px; border: 1px solid #e0e0e0; border-top: none;">
            <p style="font-size: 12px; color: #999; margin: 0;">Powered by Recovery Router</p>
        </div>
    </div>
    """
