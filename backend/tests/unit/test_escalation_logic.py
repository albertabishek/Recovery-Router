from app.services.escalation import _pick_next_channel


class TestPickNextChannel:
    def test_switches_from_whatsapp_to_email(self):
        event = {"customer_phone": "+919999", "customer_email": "a@b.com"}
        assert _pick_next_channel("whatsapp", event) == "email"

    def test_switches_from_email_to_whatsapp(self):
        event = {"customer_phone": "+919999", "customer_email": "a@b.com"}
        assert _pick_next_channel("email", event) == "whatsapp"

    def test_switches_from_sms_to_whatsapp(self):
        event = {"customer_phone": "+919999", "customer_email": "a@b.com"}
        assert _pick_next_channel("sms", event) == "whatsapp"

    def test_avoids_blocked_channels(self):
        event = {"customer_phone": "+919999", "customer_email": "a@b.com"}
        result = _pick_next_channel("whatsapp", event, avoid={"email"})
        assert result == "sms"

    def test_phone_only_no_email(self):
        event = {"customer_phone": "+919999"}
        result = _pick_next_channel("whatsapp", event)
        assert result == "sms"

    def test_email_only_no_phone(self):
        event = {"customer_email": "a@b.com"}
        result = _pick_next_channel("email", event)
        assert result == "email"

    def test_all_blocked_falls_back_to_email(self):
        event = {"customer_phone": "+919999", "customer_email": "a@b.com"}
        result = _pick_next_channel("whatsapp", event, avoid={"whatsapp", "email", "sms"})
        assert result == "email"

    def test_none_last_channel(self):
        event = {"customer_phone": "+919999", "customer_email": "a@b.com"}
        result = _pick_next_channel(None, event)
        assert result == "whatsapp"
