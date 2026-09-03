"""Unit tests for messenger.py — degradation chains, result helpers, channel routing."""
import pytest
from unittest.mock import patch, MagicMock
from app.services.messenger import (
    send_message, _try_whatsapp_chain, _try_sms_chain, _try_email_chain,
    _ok, _fail, _fail_cooldown,
    _send_green_api_whatsapp, _send_twilio_whatsapp, _send_twilio_sms, _send_via_resend,
)


class TestResultHelpers:
    def test_ok_builds_success(self):
        r = _ok({"message_id": "m1"}, "whatsapp", None, [])
        assert r["success"] is True
        assert r["message_id"] == "m1"
        assert r["channel_used"] == "whatsapp"
        assert r["degraded_from"] is None

    def test_ok_with_degradation(self):
        r = _ok({"message_id": "m2"}, "email", "whatsapp", [{"provider": "green_api", "status": "failed"}])
        assert r["degraded_from"] == "whatsapp"
        assert r["channel_used"] == "email"
        assert len(r["degradation_path"]) == 1

    def test_fail_collects_errors(self):
        path = [
            {"provider": "green_api", "status": "failed", "error": "Connection refused"},
            {"provider": "twilio_whatsapp", "status": "failed", "error": "Twilio not configured"},
        ]
        r = _fail("whatsapp", path)
        assert r["success"] is False
        assert "Connection refused" in r["error"]
        assert "Twilio not configured" in r["error"]

    def test_fail_with_extra_error(self):
        r = _fail("none", [], "Channel is none — no action needed")
        assert "no action" in r["error"]

    def test_fail_empty_path(self):
        r = _fail("whatsapp", [])
        assert r["error"] == "All providers failed"

    def test_fail_cooldown(self):
        r = _fail_cooldown("sms", [{"provider": "sms_cooldown", "status": "skipped"}])
        assert r["success"] is False
        assert r["error"] == "Cooldown active"


class TestSendMessageRouting:
    @patch("app.services.messenger._try_whatsapp_chain")
    @patch("app.services.messenger.generate_personalized_messages", return_value={})
    def test_routes_whatsapp(self, mock_gen, mock_wa):
        mock_wa.return_value = {"success": True}
        send_message(channel="whatsapp", customer_name="Test", customer_email="t@t.com",
                     customer_phone="+91999", amount=499, currency="INR",
                     failure_category="gateway_error", payment_link_url="http://link")
        mock_wa.assert_called_once()

    @patch("app.services.messenger._try_sms_chain")
    @patch("app.services.messenger.generate_personalized_messages", return_value={})
    def test_routes_sms(self, mock_gen, mock_sms):
        mock_sms.return_value = {"success": True}
        send_message(channel="sms", customer_name="Test", customer_email=None,
                     customer_phone="+91999", amount=499, currency="INR",
                     failure_category="gateway_error", payment_link_url="http://link")
        mock_sms.assert_called_once()

    @patch("app.services.messenger._try_email_chain")
    @patch("app.services.messenger.generate_personalized_messages", return_value={})
    def test_routes_email(self, mock_gen, mock_email):
        mock_email.return_value = {"success": True}
        send_message(channel="email", customer_name="Test", customer_email="t@t.com",
                     customer_phone=None, amount=499, currency="INR",
                     failure_category="gateway_error", payment_link_url="http://link")
        mock_email.assert_called_once()

    @patch("app.services.messenger.generate_personalized_messages", return_value={})
    def test_none_channel_returns_failure(self, mock_gen):
        r = send_message(channel="none", customer_name="Test", customer_email=None,
                         customer_phone=None, amount=499, currency="INR",
                         failure_category="unrecoverable", payment_link_url="")
        assert r["success"] is False
        assert "no action" in r["error"].lower()


class TestWhatsAppChain:
    @patch("app.services.messenger._send_green_api_whatsapp")
    @patch("app.services.messenger.check_per_resource_cooldown", return_value=True)
    def test_green_api_success(self, mock_cooldown, mock_green):
        mock_green.return_value = {"success": True, "message_id": "g1"}
        r = _try_whatsapp_chain("+91999", "t@t.com", {}, "http://link", [])
        assert r["success"] is True
        assert r["channel_used"] == "whatsapp"

    @patch("app.services.messenger._send_twilio_whatsapp")
    @patch("app.services.messenger._send_green_api_whatsapp")
    @patch("app.services.messenger.check_per_resource_cooldown", return_value=True)
    def test_falls_to_twilio_on_green_failure(self, mock_cooldown, mock_green, mock_twilio):
        mock_green.return_value = {"success": False, "error": "Green API down"}
        mock_twilio.return_value = {"success": True, "message_id": "t1"}
        r = _try_whatsapp_chain("+91999", "t@t.com", {}, "http://link", [])
        assert r["success"] is True

    @patch("app.services.messenger._send_via_resend")
    @patch("app.services.messenger._send_twilio_whatsapp")
    @patch("app.services.messenger._send_green_api_whatsapp")
    @patch("app.services.messenger.check_per_resource_cooldown", return_value=True)
    def test_falls_to_email_on_all_wa_failure(self, mock_cooldown, mock_green, mock_twilio, mock_resend):
        mock_green.return_value = {"success": False, "error": "down"}
        mock_twilio.return_value = {"success": False, "error": "down"}
        mock_resend.return_value = {"success": True, "message_id": "e1"}
        r = _try_whatsapp_chain("+91999", "t@t.com", {}, "http://link", [])
        assert r["success"] is True
        assert r["degraded_from"] == "whatsapp"
        assert r["channel_used"] == "email"

    def test_no_phone_falls_to_email(self):
        with patch("app.services.messenger._send_via_resend") as mock_resend:
            with patch("app.services.messenger.check_per_resource_cooldown", return_value=True):
                mock_resend.return_value = {"success": True, "message_id": "e2"}
                r = _try_whatsapp_chain(None, "t@t.com", {}, "http://link", [])
                assert r["success"] is True
                assert r["channel_used"] == "email"

    def test_no_phone_no_email_fails(self):
        r = _try_whatsapp_chain(None, None, {}, "http://link", [])
        assert r["success"] is False

    @patch("app.services.messenger._send_via_resend")
    @patch("app.services.messenger.check_per_resource_cooldown", return_value=False)
    def test_cooldown_falls_to_email(self, mock_cooldown, mock_resend):
        mock_resend.return_value = {"success": True, "message_id": "e3"}
        r = _try_whatsapp_chain("+91999", "t@t.com", {}, "http://link", [])
        assert r["success"] is False or r.get("error") == "Cooldown active"

    @patch("app.services.messenger.check_per_resource_cooldown", return_value=False)
    def test_cooldown_no_email_returns_cooldown(self, mock_cooldown):
        r = _try_whatsapp_chain("+91999", None, {}, "http://link", [])
        assert r["success"] is False
        assert r["error"] == "Cooldown active"


class TestSMSChain:
    @patch("app.services.messenger._send_twilio_sms")
    @patch("app.services.messenger.check_per_resource_cooldown", return_value=True)
    def test_sms_success(self, mock_cooldown, mock_sms):
        mock_sms.return_value = {"success": True, "message_id": "s1"}
        r = _try_sms_chain("+91999", "t@t.com", {}, "http://link", [])
        assert r["success"] is True
        assert r["channel_used"] == "sms"

    @patch("app.services.messenger._send_twilio_whatsapp")
    @patch("app.services.messenger._send_green_api_whatsapp")
    @patch("app.services.messenger._send_twilio_sms")
    @patch("app.services.messenger.check_per_resource_cooldown", return_value=True)
    def test_sms_falls_to_green_api_then_twilio_wa(self, mock_cooldown, mock_sms, mock_green, mock_twilio):
        mock_sms.return_value = {"success": False, "error": "down"}
        mock_green.return_value = {"success": False, "error": "down"}
        mock_twilio.return_value = {"success": True, "message_id": "tw1"}
        r = _try_sms_chain("+91999", "t@t.com", {}, "http://link", [])
        assert r["success"] is True
        assert r["degraded_from"] == "sms"

    def test_no_phone_falls_to_email(self):
        with patch("app.services.messenger._send_via_resend") as mock_resend:
            with patch("app.services.messenger.check_per_resource_cooldown", return_value=True):
                mock_resend.return_value = {"success": True, "message_id": "e4"}
                r = _try_sms_chain(None, "t@t.com", {}, "http://link", [])
                assert r["success"] is True
                assert r["channel_used"] == "email"


class TestEmailChain:
    @patch("app.services.messenger._send_via_resend")
    @patch("app.services.messenger.check_per_resource_cooldown", return_value=True)
    def test_email_success(self, mock_cooldown, mock_resend):
        mock_resend.return_value = {"success": True, "message_id": "e5"}
        r = _try_email_chain("t@t.com", {}, "http://link", [])
        assert r["success"] is True
        assert r["channel_used"] == "email"

    def test_no_email_fails(self):
        r = _try_email_chain(None, {}, "http://link", [])
        assert r["success"] is False

    @patch("app.services.messenger.check_per_resource_cooldown", return_value=False)
    def test_cooldown_returns_cooldown_error(self, mock_cooldown):
        r = _try_email_chain("t@t.com", {}, "http://link", [])
        assert r["error"] == "Cooldown active"


class TestProviderNotConfigured:
    def test_twilio_whatsapp_not_configured(self):
        with patch("app.services.messenger.settings") as mock_settings:
            mock_settings.TWILIO_ACCOUNT_SID = ""
            mock_settings.TWILIO_AUTH_TOKEN = ""
            r = _send_twilio_whatsapp("+91999")
            assert r["success"] is False
            assert "not configured" in r["error"]

    def test_green_api_not_configured(self):
        with patch("app.services.messenger.settings") as mock_settings:
            mock_settings.GREEN_API_INSTANCE_ID = ""
            mock_settings.GREEN_API_TOKEN = ""
            r = _send_green_api_whatsapp("+91999", {}, "http://link")
            assert r["success"] is False
            assert "not configured" in r["error"]

    def test_twilio_sms_not_configured(self):
        with patch("app.services.messenger.settings") as mock_settings:
            mock_settings.TWILIO_ACCOUNT_SID = ""
            mock_settings.TWILIO_AUTH_TOKEN = ""
            r = _send_twilio_sms("+91999", {}, "http://link")
            assert r["success"] is False
            assert "not configured" in r["error"]

    def test_resend_exception(self):
        with patch("app.services.messenger.resend") as mock_resend:
            with patch("app.services.messenger.render_email_html", return_value="<p>test</p>"):
                mock_resend.api_key = "test"
                mock_resend.Emails.send.side_effect = Exception("API key invalid")
                r = _send_via_resend("t@t.com", {}, "http://link")
                assert r["success"] is False
                assert "API key invalid" in r["error"]
