from pydantic import BaseModel, validator, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from app.models.test import TestStatus, LoadProfileType

class LoadProfileConfig(BaseModel):
    """Load profile configuration schema."""
    initial_users: Optional[int] = 1
    target_users: Optional[int] = 100
    ramp_duration: Optional[int] = 300
    hold_duration: Optional[int] = 600
    concurrent_users: Optional[int] = 100
    baseline_users: Optional[int] = 10
    spike_users: Optional[int] = 1000
    spike_duration: Optional[int] = 60
    baseline_duration: Optional[int] = 300
    duration: Optional[int] = 600
    
    class Config:
        extra = "allow"  # Allow additional fields for custom profiles

class TestDefinitionBase(BaseModel):
    name: str
    description: Optional[str] = None
    target_url: str
    method: str = "GET"
    headers: Optional[Dict[str, str]] = {}
    body_template: Optional[str] = None
    auth_type: Optional[str] = None
    auth_credentials: Optional[Dict[str, Any]] = {}
    load_profile_type: LoadProfileType
    load_profile_config: LoadProfileConfig
    duration: int = Field(gt=0, description="Duration in seconds")
    max_concurrent_users: int = Field(gt=0, default=100)
    rps_limit: int = Field(gt=0, default=1000)
    timeout: int = Field(gt=0, default=30)
    region: str = "us-east-1"
    use_proxies: bool = False
    proxy_config: Optional[Dict[str, Any]] = {}
    schedule_cron: Optional[str] = None
    test_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    notify_on_start: bool = False
    notify_on_complete: bool = True
    notify_on_failure: bool = True
    notification_channels: List[str] = []
    authorization_document_hash: Optional[str] = None
    justification: Optional[str] = None
    
    @validator('target_url')
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v
    
    @validator('method')
    def validate_method(cls, v):
        allowed_methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']
        if v.upper() not in allowed_methods:
            raise ValueError(f'Method must be one of: {", ".join(allowed_methods)}')
        return v.upper()
    
    @validator('region')
    def validate_region(cls, v):
        allowed_regions = ['us-east-1', 'us-west-2', 'eu-west-1', 'ap-southeast-1']
        if v not in allowed_regions:
            raise ValueError(f'Region must be one of: {", ".join(allowed_regions)}')
        return v

class TestDefinitionCreate(TestDefinitionBase):
    pass

class TestDefinitionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    target_url: Optional[str] = None
    method: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    body_template: Optional[str] = None
    auth_type: Optional[str] = None
    auth_credentials: Optional[Dict[str, Any]] = None
    load_profile_type: Optional[LoadProfileType] = None
    load_profile_config: Optional[LoadProfileConfig] = None
    duration: Optional[int] = Field(None, gt=0)
    max_concurrent_users: Optional[int] = Field(None, gt=0)
    rps_limit: Optional[int] = Field(None, gt=0)
    timeout: Optional[int] = Field(None, gt=0)
    region: Optional[str] = None
    use_proxies: Optional[bool] = None
    proxy_config: Optional[Dict[str, Any]] = None
    schedule_cron: Optional[str] = None
    test_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    notify_on_start: Optional[bool] = None
    notify_on_complete: Optional[bool] = None
    notify_on_failure: Optional[bool] = None
    notification_channels: Optional[List[str]] = None

class TestDefinitionResponse(TestDefinitionBase):
    id: int
    status: TestStatus
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: int
    
    class Config:
        from_attributes = True

class TestExecutionResponse(BaseModel):
    id: int
    execution_id: str
    test_definition_id: int
    status: TestStatus
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_actual: Optional[int]
    allocated_users: int
    allocated_rps: int
    runner_type: Optional[str]
    runner_instance: Optional[str]
    error_message: Optional[str]
    abort_reason: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class TestResultMetrics(BaseModel):
    timestamp: datetime
    total_requests: int
    successful_requests: int
    failed_requests: int
    requests_per_second: float
    response_time_avg: float
    response_time_p50: float
    response_time_p95: float
    response_time_p99: float
    response_time_max: float
    error_rate: float
    concurrent_users: int
    bytes_sent: int
    bytes_received: int

class TestResultResponse(BaseModel):
    id: int
    execution_id: int
    timestamp: datetime
    total_requests: int
    successful_requests: int
    failed_requests: int
    requests_per_second: float
    response_time_avg: float
    response_time_p50: float
    response_time_p95: float
    response_time_p99: float
    response_time_max: float
    error_rate: float
    error_breakdown: Optional[Dict[str, Any]]
    concurrent_users: int
    bytes_sent: int
    bytes_received: int
    custom_metrics: Optional[Dict[str, Any]]
    
    class Config:
        from_attributes = True

class TestSummary(BaseModel):
    test_definition: TestDefinitionResponse
    last_execution: Optional[TestExecutionResponse]
    total_executions: int
    successful_executions: int
    failed_executions: int
    average_duration: Optional[float]
    last_run: Optional[datetime]

class TestStartRequest(BaseModel):
    test_id: int
    overrides: Optional[Dict[str, Any]] = {}

class TestStopRequest(BaseModel):
    test_id: int
    reason: Optional[str] = "Manual stop"

class TestScheduleRequest(BaseModel):
    test_id: int
    cron_expression: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

class TestListRequest(BaseModel):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)
    status: Optional[TestStatus] = None
    created_by: Optional[int] = None
    search: Optional[str] = None
    sort_by: str = "created_at"
    sort_order: str = "desc"
    
    @validator('sort_order')
    def validate_sort_order(cls, v):
        if v not in ['asc', 'desc']:
            raise ValueError('sort_order must be either asc or desc')
        return v

class TestListResponse(BaseModel):
    tests: List[TestDefinitionResponse]
    total: int
    page: int
    limit: int
    pages: int