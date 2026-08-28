"""
AI-powered message personalization.
Generates context-aware recovery messages based on failure details,
customer context, and channel constraints.
"""

import json
import logging
from html import escape as _h
from app.services.ai_client import ai_call

logger = logging.getLogger(__name__)

MESSAGE_PROMPT = """You write recovery messages for a payment recovery system used by Indian merchants.

Your job: write a SHORT, WARM, HELPFUL message that makes the customer want to complete their payment. Not pushy. Not corporate. Like a helpful shopkeeper who noticed something went wrong.

## Context you'll receive
- channel: whatsapp, sms, or email
- failure_category: what went wrong
- amount and currency
- customer_name (use first name only if full name given)
- personalization_hint: specific insight from the classification engine
- attempt_number: 0 = first contact, 1+ = follow-up

## Channel constraints

**WhatsApp** (max 200 chars):
- Conversational, warm, direct
- Include the payment link naturally
- Use 1-2 relevant emojis max (not generic smiley — match the context)
- No formal greetings, no "Dear Sir/Madam"

**SMS** (max 140 chars):
- Ultra-brief, action-focused
- Amount + reason + link, that's it
- No emojis, no fluff

**Email** (subject + body):
- Subject: max 60 chars, specific to the failure (not generic "payment failed")
- Body: 2-3 short paragraphs. Acknowledge what happened. Explain it's easy to fix. Link.
- Warm but professional. No "We apologize for the inconvenience."

## Tone by attempt
- attempt 0: Helpful, no pressure. "Hey, looks like something went wrong."
- attempt 1: Gentle reminder. "Just following up."
- attempt 2: Slightly more direct. "Your payment is still pending."
- attempt 3+: Final, honest. "Last reminder before we close this."

## Output format
Respond with JSON:
{
  "whatsapp_text": "<message with {link} placeholder>",
  "sms_text": "<message with {link} placeholder>",
  "email_subject": "<subject line>",
  "email_greeting": "<opening line>",
  "email_body": "<main paragraph>",
  "email_cta_text": "<button text, max 25 chars>"
}

IMPORTANT: Use {link} as placeholder for the payment URL. Do NOT invent a URL."""

MESSAGE_SCHEMA = {
    "email_cta_text": {"type": "str", "default": "Complete Payment"},
}


def generate_personalized_messages(
    channel: str,
    customer_name: str | None,
    amount: float,
    currency: str,
    failure_category: str,
    personalization_hint: str | None = None,
    attempt_number: int = 0,
    reasoning: str = "",
) -> dict:
    """Generate AI-personalized messages for all channels.

    Returns dict with whatsapp_text, sms_text, email_subject, email_greeting,
    email_body, email_cta_text — all with {link} placeholder.
    Falls back to templates if AI is unavailable.
    """
    name = (customer_name or "").split()[0] if customer_name else "there"

    user_msg = json.dumps({
        "channel": channel,
        "failure_category": failure_category,
        "amount": amount,
        "currency": currency,
        "customer_name": name,
        "personalization_hint": personalization_hint or "",
        "attempt_number": attempt_number,
        "reasoning": reasoning,
    })

    result = ai_call(
        system_prompt=MESSAGE_PROMPT,
        user_message=user_msg,
        response_schema=MESSAGE_SCHEMA,
        temperature=0.4,
        max_tokens=400,
    )

    if result:
        return result

    return _fallback_messages(name, amount, currency, failure_category, attempt_number)


def _fallback_messages(
    name: str, amount: float, currency: str, category: str, attempt: int,
) -> dict:
    """Template fallback when AI is unavailable."""
    if attempt == 0:
        wa = f"Hi {name}, your payment of {currency} {amount:,.0f} didn't go through. Tap here to retry: {{link}}"
        sms = f"{currency} {amount:,.0f} payment pending. Retry: {{link}}"
        subj = f"Complete your {currency} {amount:,.0f} payment"
        greet = f"Hi {name},"
        body = f"Your recent payment of {currency} {amount:,.2f} didn't go through. These things happen — click below to try again."
    else:
        wa = f"Hi {name}, just a reminder — your {currency} {amount:,.0f} payment is still pending: {{link}}"
        sms = f"Reminder: {currency} {amount:,.0f} pending. Complete: {{link}}"
        subj = f"Reminder: {currency} {amount:,.0f} payment pending"
        greet = f"Hi {name},"
        body = f"Your payment of {currency} {amount:,.2f} is still pending. We'd love to help you complete it."

    return {
        "whatsapp_text": wa,
        "sms_text": sms,
        "email_subject": subj,
        "email_greeting": greet,
        "email_body": body,
        "email_cta_text": "Complete Payment",
    }


def render_email_html(messages: dict, payment_link_url: str) -> str:
    """Render personalized messages into the email HTML template."""
    link = _safe_url(payment_link_url)
    subj = _h(messages.get("email_subject", "Complete your payment"))
    greet = _h(messages.get("email_greeting", "Hi,"))
    body = _h(messages.get("email_body", "")).replace("\n", "<br>")
    cta = _h(messages.get("email_cta_text", "Complete Payment"))

    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: #1a1a2e; padding: 24px; border-radius: 12px 12px 0 0;">
            <h1 style="color: #fff; margin: 0; font-size: 20px;">Recovery Router</h1>
            <p style="color: #a0a0b0; margin: 4px 0 0 0; font-size: 13px;">Intelligent Payment Recovery</p>
        </div>
        <div style="background: #fff; padding: 32px; border: 1px solid #e0e0e0;">
            <p style="font-size: 16px; color: #333;">{greet}</p>
            <p style="font-size: 15px; color: #555; line-height: 1.6;">{body}</p>
            <div style="text-align: center; margin: 32px 0;">
                <a href="{link}"
                   style="background: #2563eb; color: #fff; padding: 14px 32px; border-radius: 8px;
                          text-decoration: none; font-size: 16px; font-weight: 600; display: inline-block;">
                    {cta}
                </a>
            </div>
            <p style="font-size: 13px; color: #888; line-height: 1.5;">
                This link expires within your recovery window. If you've already completed this payment, please ignore this.
            </p>
        </div>
        <div style="background: #f8f9fa; padding: 16px 32px; border-radius: 0 0 12px 12px; border: 1px solid #e0e0e0; border-top: none;">
            <p style="font-size: 12px; color: #999; margin: 0;">Powered by Recovery Router — Razorpay AI Buildathon</p>
        </div>
    </div>
    """


def _safe_url(url: str) -> str:
    if url and url.startswith(("http://", "https://")):
        return _h(url, quote=True)
    return "#"
