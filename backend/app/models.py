from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


# --- Webhook Input Models ---

class RecoveryEventInput(BaseModel):
    event_type: Literal["payment_failure", "cart_abandonment", "invoice_overdue"]
    payment_id: Optional[str] = None
    order_id: Optional[str] = None
    invoice_id: Optional[str] = None
    amount: float = 0
    currency: str = "INR"
    method: Optional[str] = None
    error_code: Optional[str] = None
    error_description: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_name: Optional[str] = "Unknown"
    cart_value: Optional[float] = None
    items_in_cart: Optional[int] = None
    days_overdue: Optional[int] = None


# --- AI Classification Models ---

class ClassificationResult(BaseModel):
    leak_type: Literal["payment_failure", "cart_abandonment", "invoice_overdue"]
    failure_category: str
    recovery_probability: float = Field(ge=0.0, le=1.0)
    recommended_action: str
    recommended_channel: Literal["whatsapp", "email", "sms", "none"]
    recommended_timing: Literal[
        "immediate", "5_minutes", "30_minutes", "1_hour", "4_hours"
    ]
    reasoning: str
    alternative_action: Optional[str] = None
    skip_reason: Optional[str] = None
    personalization_hint: Optional[str] = None
    fallback_used: bool = False


# --- Action Routing ---

class ActionPlan(BaseModel):
    action: Literal["send_now", "send_delayed", "no_action"]
    channel: Optional[Literal["whatsapp", "email", "sms"]] = None
    delay_seconds: int = 0
    skip_reason: Optional[str] = None


# --- API Response Models ---

class WebhookResponse(BaseModel):
    status: str
    message: str
    event_id: Optional[int] = None


class AnalyticsSummary(BaseModel):
    total_events: int = 0
    recovered_count: int = 0
    pending_count: int = 0
    exhausted_count: int = 0
    no_action_count: int = 0
    recovery_rate_percent: float = 0.0
    total_amount: float = 0.0
    recovered_amount: float = 0.0
    pending_amount: float = 0.0
    avg_attempts_to_recover: float = 0.0
    avg_recovery_time_hours: float = 0.0


class AILift(BaseModel):
    baseline_rate_percent: float = 15.0
    ai_recovery_rate_percent: float = 0.0
    improvement_points: float = 0.0
    lift_multiplier: float = 0.0
    additional_revenue_recovered: float = 0.0
    baseline_source: str = "Industry reference: ~15% organic recovery via simple retries (Razorpay blog, observational — not a controlled baseline)"


class AnalyticsResponse(BaseModel):
    summary: AnalyticsSummary
    ai_lift: AILift
    by_event_type: dict = {}
    by_channel: dict = {}
    channel_ranking: list = []
    by_failure_category: dict = {}
    generated_at: str = ""


class EventListItem(BaseModel):
    id: int
    event_type: str
    amount: float
    currency: str
    customer_name: Optional[str] = None
    failure_category: Optional[str] = None
    recommended_channel: Optional[str] = None
    status: str
    recovery_probability: Optional[float] = None
    attempt_count: int = 0
    created_at: str
    recovered_at: Optional[str] = None
    recovered_amount: Optional[float] = None


class SimulateRequest(BaseModel):
    event_type: Literal["payment_failure", "cart_abandonment", "invoice_overdue"]
    scenario: str = "upi_timeout"
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    services: dict = {}
