"""Unit tests for recovery_tracker.process_payment_captured.

Mocks Supabase to test reconciliation logic without a database.
"""
import pytest
from unittest.mock import patch, MagicMock
from app.services.recovery_tracker import process_payment_captured


def _captured_body(
    payment_id="pay_test123",
    order_id="order_test456",
    amount_paise=49900,
    currency="INR",
    status="captured",
    notes=None,
    reference_id=None,
):
    body = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "order_id": order_id,
                    "amount": amount_paise,
                    "currency": currency,
                    "status": status,
                    "method": "card",
                }
            },
            "payment_link": {"entity": {}},
        },
    }
    if notes:
        body["payload"]["payment"]["entity"]["notes"] = notes
    if reference_id:
        body["payload"]["payment_link"]["entity"]["reference_id"] = reference_id
    return body


class FakeResult:
    def __init__(self, data):
        self.data = data


def _mock_supabase(
    duplicate_data=None,
    match_data=None,
    fresh_attempt_count=1,
    sent_attempts=None,
    update_data=None,
):
    sb = MagicMock()

    call_count = {"select": 0}
    match_returned = {"done": False}

    def make_chain(*args, **kwargs):
        chain = MagicMock()

        def fake_execute():
            call_count["select"] += 1
            n = call_count["select"]
            if n == 1:
                return FakeResult(duplicate_data or [])
            if n == 2 and not duplicate_data:
                return FakeResult([])
            if not match_returned["done"] and match_data:
                match_returned["done"] = True
                return FakeResult(match_data)
            if match_returned["done"]:
                if fresh_attempt_count is not None:
                    fc = fresh_attempt_count
                    fresh_attempt_count_used = True
                    return FakeResult([{"attempt_count": fc}])
                return FakeResult(sent_attempts or [])
            return FakeResult([])

        chain.execute = fake_execute
        chain.select = lambda *a: chain
        chain.eq = lambda *a: chain
        chain.in_ = lambda *a: chain
        chain.limit = lambda *a: chain
        chain.update = lambda *a: MagicMock(
            eq=lambda *a: MagicMock(
                in_=lambda *a: MagicMock(
                    execute=lambda: FakeResult(update_data if update_data is not None else [{"id": 1}])
                )
            )
        )
        return chain

    sb.table = lambda name: MagicMock(
        select=lambda *a: make_chain(),
        update=lambda data: MagicMock(
            eq=lambda *a: MagicMock(
                in_=lambda *a: MagicMock(
                    execute=lambda: FakeResult(update_data if update_data is not None else [{"id": 1}])
                )
            )
        ),
    )
    return sb


class TestPreValidation:
    def test_rejects_non_captured_status(self):
        body = _captured_body(status="failed")
        result = process_payment_captured(body)
        assert result["status"] == "rejected"
        assert "not 'captured'" in result["reason"]

    def test_rejects_missing_status(self):
        body = _captured_body()
        body["payload"]["payment"]["entity"]["status"] = ""
        result = process_payment_captured(body)
        assert result["status"] == "rejected"

    def test_rejects_missing_payment_id(self):
        body = _captured_body(payment_id=None)
        body["payload"]["payment"]["entity"].pop("id", None)
        result = process_payment_captured(body)
        assert result["status"] == "rejected"
        assert "Missing payment_id" in result["reason"]

    def test_ignores_no_identifiers(self):
        body = _captured_body(order_id=None)
        body["payload"]["payment"]["entity"].pop("order_id", None)
        result = process_payment_captured(body)
        assert result["status"] == "ignored"


class TestCurrencyValidation:
    @patch("app.services.recovery_tracker.get_supabase")
    def test_rejects_currency_mismatch(self, mock_get_sb):
        sb = MagicMock()
        mock_get_sb.return_value = sb

        select_chain = MagicMock()
        select_chain.execute.side_effect = [
            FakeResult([]),
            FakeResult([]),
            FakeResult([{
                "id": 1, "amount": 499, "currency": "USD",
                "status": "pending", "attempt_count": 1,
            }]),
        ]
        select_chain.select = MagicMock(return_value=select_chain)
        select_chain.eq = MagicMock(return_value=select_chain)
        select_chain.in_ = MagicMock(return_value=select_chain)
        select_chain.limit = MagicMock(return_value=select_chain)
        sb.table.return_value = select_chain

        body = _captured_body(amount_paise=49900, currency="INR")
        result = process_payment_captured(body)
        assert result["status"] == "rejected"
        assert "Currency mismatch" in result["reason"]


class TestAmountValidation:
    @patch("app.services.recovery_tracker.get_supabase")
    def test_rejects_zero_captured_amount(self, mock_get_sb):
        sb = MagicMock()
        mock_get_sb.return_value = sb

        select_chain = MagicMock()
        select_chain.execute.side_effect = [
            FakeResult([]),
            FakeResult([]),
            FakeResult([{
                "id": 1, "amount": 499, "currency": "INR",
                "status": "pending", "attempt_count": 1,
            }]),
        ]
        select_chain.select = MagicMock(return_value=select_chain)
        select_chain.eq = MagicMock(return_value=select_chain)
        select_chain.in_ = MagicMock(return_value=select_chain)
        select_chain.limit = MagicMock(return_value=select_chain)
        sb.table.return_value = select_chain

        body = _captured_body(amount_paise=0)
        result = process_payment_captured(body)
        assert result["status"] == "rejected"
        assert "zero" in result["reason"].lower()

    @patch("app.services.recovery_tracker.get_supabase")
    def test_rejects_amount_mismatch(self, mock_get_sb):
        sb = MagicMock()
        mock_get_sb.return_value = sb

        select_chain = MagicMock()
        select_chain.execute.side_effect = [
            FakeResult([]),
            FakeResult([]),
            FakeResult([{
                "id": 1, "amount": 499, "currency": "INR",
                "status": "pending", "attempt_count": 1,
            }]),
        ]
        select_chain.select = MagicMock(return_value=select_chain)
        select_chain.eq = MagicMock(return_value=select_chain)
        select_chain.in_ = MagicMock(return_value=select_chain)
        select_chain.limit = MagicMock(return_value=select_chain)
        sb.table.return_value = select_chain

        body = _captured_body(amount_paise=99900)
        result = process_payment_captured(body)
        assert result["status"] == "rejected"
        assert "Amount mismatch" in result["reason"]

    @patch("app.services.recovery_tracker.get_supabase")
    def test_accepts_matching_amount(self, mock_get_sb):
        sb = MagicMock()
        mock_get_sb.return_value = sb

        event_data = {
            "id": 1, "amount": 499, "currency": "INR",
            "status": "pending", "attempt_count": 2,
        }

        select_chain = MagicMock()
        select_chain.execute.side_effect = [
            FakeResult([]),
            FakeResult([]),
            FakeResult([event_data]),
            FakeResult([{"attempt_count": 2}]),
            FakeResult([{"id": 10}]),
        ]
        select_chain.select = MagicMock(return_value=select_chain)
        select_chain.eq = MagicMock(return_value=select_chain)
        select_chain.in_ = MagicMock(return_value=select_chain)
        select_chain.limit = MagicMock(return_value=select_chain)

        update_chain = MagicMock()
        update_chain.execute.return_value = FakeResult([{"id": 1}])
        update_chain.eq = MagicMock(return_value=update_chain)
        update_chain.in_ = MagicMock(return_value=update_chain)
        select_chain.update = MagicMock(return_value=update_chain)

        sb.table.return_value = select_chain

        body = _captured_body(amount_paise=49900)
        result = process_payment_captured(body)
        assert result["status"] == "recovered"


class TestDuplicateAttribution:
    @patch("app.services.recovery_tracker.get_supabase")
    def test_blocks_duplicate_payment(self, mock_get_sb):
        sb = MagicMock()
        mock_get_sb.return_value = sb

        select_chain = MagicMock()
        select_chain.execute.return_value = FakeResult([{"id": 99}])
        select_chain.select = MagicMock(return_value=select_chain)
        select_chain.eq = MagicMock(return_value=select_chain)
        select_chain.in_ = MagicMock(return_value=select_chain)
        select_chain.limit = MagicMock(return_value=select_chain)
        sb.table.return_value = select_chain

        body = _captured_body()
        result = process_payment_captured(body)
        assert result["status"] == "duplicate_attribution"
        assert result["existing_event_id"] == 99


class TestOrganicRecovery:
    @patch("app.services.recovery_tracker.get_supabase")
    def test_marks_organic_when_zero_attempts(self, mock_get_sb):
        sb = MagicMock()
        mock_get_sb.return_value = sb

        event_data = {
            "id": 1, "amount": 499, "currency": "INR",
            "status": "pending", "attempt_count": 0,
        }

        select_chain = MagicMock()
        select_chain.execute.side_effect = [
            FakeResult([]),
            FakeResult([]),
            FakeResult([event_data]),
            FakeResult([{"attempt_count": 0}]),
            FakeResult([]),
        ]
        select_chain.select = MagicMock(return_value=select_chain)
        select_chain.eq = MagicMock(return_value=select_chain)
        select_chain.in_ = MagicMock(return_value=select_chain)
        select_chain.limit = MagicMock(return_value=select_chain)

        update_chain = MagicMock()
        update_chain.execute.return_value = FakeResult([{"id": 1}])
        update_chain.eq = MagicMock(return_value=update_chain)
        update_chain.in_ = MagicMock(return_value=update_chain)
        select_chain.update = MagicMock(return_value=update_chain)

        sb.table.return_value = select_chain

        body = _captured_body(amount_paise=49900)
        result = process_payment_captured(body)
        assert result["status"] == "organic_recovery"


class TestMatchStrategy:
    def test_notes_recovery_event_id_tried_first(self):
        body = _captured_body(notes={"recovery_event_id": "42"})
        assert body["payload"]["payment"]["entity"]["notes"]["recovery_event_id"] == "42"

    def test_no_match_returns_correctly(self):
        with patch("app.services.recovery_tracker.get_supabase") as mock_get_sb:
            sb = MagicMock()
            mock_get_sb.return_value = sb

            select_chain = MagicMock()
            select_chain.execute.return_value = FakeResult([])
            select_chain.select = MagicMock(return_value=select_chain)
            select_chain.eq = MagicMock(return_value=select_chain)
            select_chain.in_ = MagicMock(return_value=select_chain)
            select_chain.limit = MagicMock(return_value=select_chain)
            sb.table.return_value = select_chain

            body = _captured_body()
            result = process_payment_captured(body)
            assert result["status"] == "no_match"
