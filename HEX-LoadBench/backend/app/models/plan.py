from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Float, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()

class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"
    
    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    
    # Plan limits
    max_daily_rps = Column(Integer, default=1000)
    max_concurrent_tests = Column(Integer, default=1)
    max_test_duration = Column(Integer, default=600)  # Duration in seconds
    max_users_per_organization = Column(Integer, default=5)
    max_api_keys = Column(Integer, default=3)
    
    # Features
    allow_custom_load_profiles = Column(Boolean, default=False)
    allow_advanced_scheduling = Column(Boolean, default=False)
    allow_real_time_monitoring = Column(Boolean, default=True)
    allow_export_reports = Column(Boolean, default=True)
    allow_api_access = Column(Boolean, default=True)
    allow_webhook_notifications = Column(Boolean, default=False)
    
    # Billing
    monthly_cost = Column(Float, default=0.0)
    yearly_cost = Column(Float, default=0.0)
    currency = Column(String(3), default="USD")
    
    # Status
    is_active = Column(Boolean, default=True)
    is_public = Column(Boolean, default=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class UserSubscription(Base):
    __tablename__ = "user_subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    organization_id = Column(Integer, ForeignKey("organizations.id"))
    plan_id = Column(String(50), ForeignKey("subscription_plans.plan_id"))
    
    # Subscription details
    status = Column(String(20), default="active")  # active, expired, cancelled, suspended
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=True)  # null for lifetime
    trial_end_date = Column(DateTime, nullable=True)
    
    # Billing cycle
    billing_cycle = Column(String(10), default="monthly")  # monthly, yearly
    next_billing_date = Column(DateTime, nullable=True)
    
    # Usage tracking
    current_daily_rps = Column(Integer, default=0)
    current_concurrent_tests = Column(Integer, default=0)
    last_usage_reset = Column(DateTime, default=datetime.utcnow)
    
    # Payment
    payment_method_id = Column(String(100), nullable=True)
    auto_renew = Column(Boolean, default=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))
    
    # Relationships
    user = relationship("User", back_populates="subscriptions")
    plan = relationship("SubscriptionPlan")

class UsageMetric(Base):
    __tablename__ = "usage_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    organization_id = Column(Integer, ForeignKey("organizations.id"))
    
    # Metric details
    metric_type = Column(String(50))  # rps, tests, users, storage
    metric_value = Column(Integer, default=0)
    metric_date = Column(DateTime, default=datetime.utcnow)
    
    # Period
    period_type = Column(String(10))  # daily, weekly, monthly
    period_start = Column(DateTime)
    period_end = Column(DateTime)
    
    # Additional data
    metadata = Column(Text)  # JSON string for additional context

# Plan configuration utilities
def get_plan_limits(plan_id: str):
    """Get plan limits for a given plan ID."""
    default_limits = {
        "free": {
            "max_daily_rps": 1000,
            "max_concurrent_tests": 1,
            "max_test_duration": 600,
            "max_users_per_organization": 5,
            "max_api_keys": 3
        },
        "basic": {
            "max_daily_rps": 10000,
            "max_concurrent_tests": 2,
            "max_test_duration": 3600,
            "max_users_per_organization": 20,
            "max_api_keys": 10
        },
        "pro": {
            "max_daily_rps": 100000,
            "max_concurrent_tests": 5,
            "max_test_duration": 14400,
            "max_users_per_organization": 100,
            "max_api_keys": 25
        },
        "vip": {
            "max_daily_rps": 500000,
            "max_concurrent_tests": 10,
            "max_test_duration": 86400,
            "max_users_per_organization": 1000,
            "max_api_keys": 100
        }
    }
    return default_limits.get(plan_id, default_limits["free"])