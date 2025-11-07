from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import datetime

class SubscriptionPlanBase(BaseModel):
    plan_id: str
    name: str
    description: Optional[str] = None
    max_daily_rps: int
    max_concurrent_tests: int
    max_test_duration: int
    max_users_per_organization: int
    max_api_keys: int
    allow_custom_load_profiles: bool = False
    allow_advanced_scheduling: bool = False
    allow_real_time_monitoring: bool = True
    allow_export_reports: bool = True
    allow_api_access: bool = True
    allow_webhook_notifications: bool = False
    monthly_cost: float = 0.0
    yearly_cost: float = 0.0
    currency: str = "USD"
    is_active: bool = True
    is_public: bool = True

class SubscriptionPlanCreate(SubscriptionPlanBase):
    pass

class SubscriptionPlanUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    max_daily_rps: Optional[int] = None
    max_concurrent_tests: Optional[int] = None
    max_test_duration: Optional[int] = None
    max_users_per_organization: Optional[int] = None
    max_api_keys: Optional[int] = None
    allow_custom_load_profiles: Optional[bool] = None
    allow_advanced_scheduling: Optional[bool] = None
    allow_real_time_monitoring: Optional[bool] = None
    allow_export_reports: Optional[bool] = None
    allow_api_access: Optional[bool] = None
    allow_webhook_notifications: Optional[bool] = None
    monthly_cost: Optional[float] = None
    yearly_cost: Optional[float] = None
    currency: Optional[str] = None
    is_active: Optional[bool] = None
    is_public: Optional[bool] = None

class SubscriptionPlanResponse(SubscriptionPlanBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class UserSubscriptionBase(BaseModel):
    plan_id: str
    billing_cycle: str = "monthly"
    auto_renew: bool = True
    
    @validator('billing_cycle')
    def validate_billing_cycle(cls, v):
        if v not in ['monthly', 'yearly']:
            raise ValueError('billing_cycle must be either monthly or yearly')
        return v

class UserSubscriptionCreate(UserSubscriptionBase):
    user_id: int
    organization_id: Optional[int] = None

class UserSubscriptionUpdate(BaseModel):
    plan_id: Optional[str] = None
    billing_cycle: Optional[str] = None
    auto_renew: Optional[bool] = None
    status: Optional[str] = None

class UserSubscriptionResponse(UserSubscriptionBase):
    id: int
    user_id: int
    organization_id: Optional[int]
    status: str
    start_date: datetime
    end_date: Optional[datetime]
    trial_end_date: Optional[datetime]
    next_billing_date: Optional[datetime]
    current_daily_rps: int
    current_concurrent_tests: int
    last_usage_reset: datetime
    payment_method_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class UserSubscriptionWithPlan(UserSubscriptionResponse):
    plan: SubscriptionPlanResponse

class UsageMetricBase(BaseModel):
    metric_type: str
    metric_value: int
    metric_date: datetime
    period_type: str = "daily"
    period_start: datetime
    period_end: datetime
    metadata: Optional[str] = None

class UsageMetricResponse(UsageMetricBase):
    id: int
    user_id: int
    organization_id: Optional[int]
    
    class Config:
        from_attributes = True

class UsageLimits(BaseModel):
    max_daily_rps: int
    max_concurrent_tests: int
    max_test_duration: int
    max_users_per_organization: int
    max_api_keys: int

class CurrentUsage(BaseModel):
    daily_rps: int
    concurrent_tests: int
    test_duration: int
    users_in_organization: int
    api_keys_active: int

class UsageReport(BaseModel):
    limits: UsageLimits
    current: CurrentUsage
    remaining: UsageLimits
    usage_percentage: dict
    
    @validator('usage_percentage')
    def calculate_usage_percentage(cls, v, values):
        if 'limits' in values and 'current' in values:
            limits = values['limits']
            current = values['current']
            
            return {
                'daily_rps': (current.daily_rps / limits.max_daily_rps) * 100 if limits.max_daily_rps > 0 else 0,
                'concurrent_tests': (current.concurrent_tests / limits.max_concurrent_tests) * 100 if limits.max_concurrent_tests > 0 else 0,
                'test_duration': (current.test_duration / limits.max_test_duration) * 100 if limits.max_test_duration > 0 else 0,
                'users_in_organization': (current.users_in_organization / limits.max_users_per_organization) * 100 if limits.max_users_per_organization > 0 else 0,
                'api_keys_active': (current.api_keys_active / limits.max_api_keys) * 100 if limits.max_api_keys > 0 else 0
            }
        return v

class PlanChangeRequest(BaseModel):
    new_plan_id: str
    reason: Optional[str] = None
    immediate_change: bool = False

class PlanChangeResponse(BaseModel):
    old_plan_id: str
    new_plan_id: str
    change_date: datetime
    effective_date: datetime
    prorated_charge: Optional[float]
    confirmation_id: str