from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Enum as SQLEnum, Float, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()

class TestStatus(enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"
    CANCELLED = "cancelled"

class LoadProfileType(enum.Enum):
    RAMP_UP = "ramp_up"
    STEADY_STATE = "steady_state"
    SPIKE = "spike"
    SOAK = "soak"
    CUSTOM = "custom"

class TestDefinition(Base):
    __tablename__ = "test_definitions"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Target configuration
    target_url = Column(String(2048), nullable=False)
    method = Column(String(10), default="GET")
    headers = Column(JSON)  # JSON object of headers
    body_template = Column(Text)
    auth_type = Column(String(50))  # bearer, basic, api_key, etc.
    auth_credentials = Column(JSON)  # JSON object of auth credentials
    
    # Load profile configuration
    load_profile_type = Column(SQLEnum(LoadProfileType), nullable=False)
    load_profile_config = Column(JSON)  # JSON object of load profile settings
    
    # Test parameters
    duration = Column(Integer, nullable=False)  # Duration in seconds
    max_concurrent_users = Column(Integer, default=100)
    rps_limit = Column(Integer, default=1000)
    timeout = Column(Integer, default=30)
    
    # Region and infrastructure
    region = Column(String(50), default="us-east-1")
    use_proxies = Column(Boolean, default=False)
    proxy_config = Column(JSON)
    
    # Scheduling
    schedule_cron = Column(String(100))  # Cron expression
    test_date = Column(DateTime)  # Specific test date
    expiration_date = Column(DateTime)
    
    # Notification settings
    notify_on_start = Column(Boolean, default=False)
    notify_on_complete = Column(Boolean, default=True)
    notify_on_failure = Column(Boolean, default=True)
    notification_channels = Column(JSON)  # Array of notification channels
    
    # Status and lifecycle
    status = Column(SQLEnum(TestStatus), default=TestStatus.DRAFT)
    is_active = Column(Boolean, default=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    created_by_user = relationship("User", back_populates="test_definitions")
    executions = relationship("TestExecution", back_populates="test_definition")
    
    # Audit fields
    authorization_document_hash = Column(String(255))
    justification = Column(Text)

class TestExecution(Base):
    __tablename__ = "test_executions"
    
    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(String(100), unique=True, index=True)  # Unique execution identifier
    
    # Test reference
    test_definition_id = Column(Integer, ForeignKey("test_definitions.id"))
    test_definition = relationship("TestDefinition", back_populates="executions")
    
    # Execution details
    status = Column(SQLEnum(TestStatus), default=TestStatus.SCHEDULED)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_actual = Column(Integer, nullable=True)  # Actual duration in seconds
    
    # Configuration snapshot
    config_snapshot = Column(JSON)  # Full configuration at time of execution
    
    # Resource allocation
    allocated_users = Column(Integer, default=0)
    allocated_rps = Column(Integer, default=0)
    runner_type = Column(String(50))  # k6, python, go
    runner_instance = Column(String(100))
    
    # Status tracking
    error_message = Column(Text)
    abort_reason = Column(Text)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    results = relationship("TestResult", back_populates="execution")

class TestResult(Base):
    __tablename__ = "test_results"
    
    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(Integer, ForeignKey("test_executions.id"))
    execution = relationship("TestExecution", back_populates="results")
    
    # Timing
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Core metrics
    total_requests = Column(Integer, default=0)
    successful_requests = Column(Integer, default=0)
    failed_requests = Column(Integer, default=0)
    
    # Performance metrics
    requests_per_second = Column(Float, default=0.0)
    response_time_avg = Column(Float, default=0.0)  # Average response time in ms
    response_time_p50 = Column(Float, default=0.0)
    response_time_p95 = Column(Float, default=0.0)
    response_time_p99 = Column(Float, default=0.0)
    response_time_max = Column(Float, default=0.0)
    
    # Error metrics
    error_rate = Column(Float, default=0.0)  # Error rate as percentage
    error_breakdown = Column(JSON)  # Detailed error breakdown
    
    # Resource metrics
    concurrent_users = Column(Integer, default=0)
    bytes_sent = Column(Integer, default=0)
    bytes_received = Column(Integer, default=0)
    
    # Custom metrics
    custom_metrics = Column(JSON)  # Additional custom metrics
    
    # Raw data (for detailed analysis)
    raw_metrics = Column(JSON)  # Raw metrics from runner
    
    # Indexes for performance
    __table_args__ = (
        {"schema": None},
    )

# Utility functions for test configuration
def create_default_load_profile(profile_type: LoadProfileType):
    """Create default load profile configuration."""
    configs = {
        LoadProfileType.RAMP_UP: {
            "initial_users": 1,
            "target_users": 100,
            "ramp_duration": 300,
            "hold_duration": 600
        },
        LoadProfileType.STEADY_STATE: {
            "concurrent_users": 100,
            "duration": 600
        },
        LoadProfileType.SPIKE: {
            "baseline_users": 10,
            "spike_users": 1000,
            "spike_duration": 60,
            "baseline_duration": 300
        },
        LoadProfileType.SOAK: {
            "concurrent_users": 50,
            "duration": 86400  # 24 hours
        },
        LoadProfileType.CUSTOM: {}
    }
    return configs.get(profile_type, {})