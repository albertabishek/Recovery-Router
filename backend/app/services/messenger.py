"""
Multi-provider messenger with AI-personalized messages.
Provider hierarchy:
  WhatsApp: Green API (personalized text) → Twilio WhatsApp (template) → Email
  SMS:      Twilio SMS → Green API WhatsApp → Twilio WhatsApp → Email
  Email:    Resend (primary, with AI-personalized content)
"""

import logging
import httpx
import resend
from twilio.rest import Client as TwilioClient
from app.config import settings
from app.utils.rate_limiter import check_per_resource_cooldown
from app.services.message_generator import generate_personalized_messages, render_email_html

logger = logging.getLogger(__name__)

TWILIO_WHATSAPP_CONTENT_SID = "HXfe5ab5f00277942d4d4200328b4d403c"


def send_message(
    channel: str,
    customer_name: str,
    customer_email: str | None,
    customer_phone: str | None,
    amount: float,
    currency: str,
    failure_category: str,
    payment_link_url: str,
    reasoning: str = "",
    attempt_number: int = 0,
    personalization_hint: str | None = None,
) -> dict:
    """Send a recovery message via the specified channel with multi-provider fallback.

    Returns {success, message_id, error, channel_used, degraded_from, degradation_path}.
    """
    messages = generate_personalized_messages(
        channel=channel,
        customer_name=customer_name,
        amount=amount,
        currency=currency,
        failure_category=failure_category,
        personalization_hint=personalization_hint,
        attempt_number=attempt_number,
        reasoning=reasoning,
    )

    degradation_path = []

    if channel == "whatsapp":
        return _try_whatsapp_chain(
            customer_phone, customer_email, messages,
            payment_link_url, degradation_path,
        )

    if channel == "sms":
        return _try_sms_chain(
            customer_phone, customer_email, messages,
            payment_link_url, degradation_path,
        )

    if channel == "email":
        return _try_email_chain(
            customer_email, messages, payment_link_url, degradation_path,
        )

    return _fail("none", degradation_path, "Channel is none — no action needed")


def _try_whatsapp_chain(phone, email, messages, link, path):
    """WhatsApp: Green API (personalized text) → Twilio WhatsApp (template) → Email fallback."""
    intended = "whatsapp"

    if not phone:
        path.append({"provider": "all_whatsapp", "status": "skipped", "error": "No phone"})
        if email:
            return _try_email_chain(email, messages, link, path, degraded_from=intended)
        return _fail(intended, path)

    if not check_per_resource_cooldown("whatsapp", phone, 300):
        path.append({"provider": "whatsapp_cooldown", "status": "skipped", "error": "Cooldown active"})
        if email:
            return _try_email_chain(email, messages, link, path, degraded_from=intended)
        return _fail_cooldown(intended, path)

    r = _send_green_api_whatsapp(phone, messages, link)
    path.append({"provider": "green_api", "status": "sent" if r["success"] else "failed", "error": r.get("error")})
    if r["success"]:
        return _ok(r, "whatsapp", None, path)

    r = _send_twilio_whatsapp(phone)
    path.append({"provider": "twilio_whatsapp", "status": "sent" if r["success"] else "failed", "error": r.get("error")})
    if r["success"]:
        return _ok(r, "whatsapp", None, path)

    if email:
        return _try_email_chain(email, messages, link, path, degraded_from=intended)

    return _fail(intended, path)


def _try_sms_chain(phone, email, messages, link, path):
    """SMS: Twilio SMS → Green API WhatsApp → Twilio WhatsApp → Email fallback."""
    intended = "sms"

    if not phone:
        path.append({"provider": "all_sms", "status": "skipped", "error": "No phone"})
        if email:
            return _try_email_chain(email, messages, link, path, degraded_from=intended)
        return _fail(intended, path)

    if not check_per_resource_cooldown("sms", phone, 300):
        path.append({"provider": "sms_cooldown", "status": "skipped", "error": "Cooldown active"})
        if email:
            return _try_email_chain(email, messages, link, path, degraded_from=intended)
        return _fail_cooldown(intended, path)

    r = _send_twilio_sms(phone, messages, link)
    path.append({"provider": "twilio_sms", "status": "sent" if r["success"] else "failed", "error": r.get("error")})
    if r["success"]:
        return _ok(r, "sms", None, path)

    r = _send_green_api_whatsapp(phone, messages, link)
    path.append({"provider": "green_api_fallback", "status": "sent" if r["success"] else "failed", "error": r.get("error")})
    if r["success"]:
        return _ok(r, "whatsapp", intended, path)

    r = _send_twilio_whatsapp(phone)
    path.append({"provider": "twilio_whatsapp_fallback", "status": "sent" if r["success"] else "failed", "error": r.get("error")})
    if r["success"]:
        return _ok(r, "whatsapp", intended, path)

    if email:
        return _try_email_chain(email, messages, link, path, degraded_from=intended)

    return _fail(intended, path)


def _try_email_chain(email, messages, link, path, degraded_from=None):
    """Email: Resend with AI-personalized content."""
    if not email:
        path.append({"provider": "all_email", "status": "skipped", "error": "No email"})
        return _fail(degraded_from or "email", path)

    if not check_per_resource_cooldown("email", email, 300):
        path.append({"provider": "email_cooldown", "status": "skipped", "error": "Cooldown active"})
        return _fail_cooldown(degraded_from or "email", path)

    r = _send_via_resend(email, messages, link)
    path.append({"provider": "resend", "status": "sent" if r["success"] else "failed", "error": r.get("error")})
    if r["success"]:
        return _ok(r, "email", degraded_from, path)

    return _fail(degraded_from or "email", path)


# --- Result helpers ---

def _ok(result, channel_used, degraded_from, path):
    return {
        "success": True,
        "message_id": result.get("message_id"),
        "error": None,
        "channel_used": channel_used,
        "degraded_from": degraded_from,
        "degradation_path": path,
    }


def _fail(intended, path, extra_error=None):
    errors = [p["error"] for p in path if p.get("error")]
    if extra_error:
        errors.append(extra_error)
    return {
        "success": False, "message_id": None,
        "error": "; ".join(errors) or "All providers failed",
        "channel_used": intended, "degraded_from": None,
        "degradation_path": path,
    }


def _fail_cooldown(intended, path):
    return {
        "success": False, "message_id": None,
        "error": "Cooldown active",
        "channel_used": intended, "degraded_from": None,
        "degradation_path": path,
    }


# --- Provider implementations ---

def _send_twilio_whatsapp(phone):
    """Send WhatsApp via Twilio using content_sid template (trial requirement)."""
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        return {"success": False, "message_id": None, "error": "Twilio not configured"}

    try:
        client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        msg = client.messages.create(
            to=f"whatsapp:{phone}",
            from_=f"whatsapp:{settings.TWILIO_PHONE_NUMBER}",
            content_sid=TWILIO_WHATSAPP_CONTENT_SID,
        )
        logger.info("Twilio WhatsApp sent: %s", msg.sid)
        return {"success": True, "message_id": msg.sid, "error": None}

    except Exception as e:
        logger.error("Twilio WhatsApp failed: %s", e)
        return {"success": False, "message_id": None, "error": str(e)}


def _send_green_api_whatsapp(phone, messages, link):
    """Send WhatsApp via Green API with AI-personalized text."""
    if not settings.GREEN_API_INSTANCE_ID or not settings.GREEN_API_TOKEN:
        return {"success": False, "message_id": None, "error": "Green API not configured"}

    try:
        clean_phone = phone.lstrip("+")
        chat_id = f"{clean_phone}@c.us"

        wa_text = messages.get("whatsapp_text", "Payment pending: {link}")
        body = wa_text.replace("{link}", link)

        url = (
            f"{settings.GREEN_API_URL}/waInstance{settings.GREEN_API_INSTANCE_ID}"
            f"/sendMessage/{settings.GREEN_API_TOKEN}"
        )
        resp = httpx.post(url, json={"chatId": chat_id, "message": body}, timeout=15)

        if resp.status_code == 200:
            data = resp.json()
            msg_id = data.get("idMessage", "")
            logger.info("Green API WhatsApp sent: %s", msg_id)
            return {"success": True, "message_id": f"greenapi:{msg_id}", "error": None}

        logger.error("Green API error: %d %s", resp.status_code, resp.text[:200])
        return {"success": False, "message_id": None, "error": f"Green API HTTP {resp.status_code}"}

    except Exception as e:
        logger.error("Green API failed: %s", e)
        return {"success": False, "message_id": None, "error": str(e)}


def _send_twilio_sms(phone, messages=None, link=""):
    """Send SMS via Twilio with the AI-generated message text."""
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        return {"success": False, "message_id": None, "error": "Twilio not configured"}

    try:
        sms_text = (messages or {}).get("sms_text", "Payment pending. Complete here: {link}")
        body = sms_text.replace("{link}", link)

        client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        msg = client.messages.create(
            to=phone,
            from_=settings.TWILIO_PHONE_NUMBER,
            body=body,
        )
        logger.info("Twilio SMS sent: %s", msg.sid)
        return {"success": True, "message_id": msg.sid, "error": None}

    except Exception as e:
        logger.error("Twilio SMS failed: %s", e)
        return {"success": False, "message_id": None, "error": str(e)}


def _send_via_resend(email, messages, link):
    """Send email via Resend with AI-personalized content."""
    try:
        resend.api_key = settings.RESEND_API_KEY
        html = render_email_html(messages, link)
        subject = messages.get("email_subject", "Complete your payment")

        r = resend.Emails.send({
            "from": settings.RESEND_FROM_EMAIL,
            "to": email,
            "subject": subject,
            "html": html,
        })
        email_id = r.get("id") if isinstance(r, dict) else str(r)
        logger.info("Resend email sent: %s", email_id)
        return {"success": True, "message_id": email_id, "error": None}

    except Exception as e:
        logger.error("Resend failed: %s", e)
        return {"success": False, "message_id": None, "error": str(e)}
