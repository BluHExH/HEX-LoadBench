from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()

class AuditAction(enum.Enum):
    # User actions
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"
    
    # Organization actions
    ORG_CREATE = "org_create"
    ORG_UPDATE = "org_update"
    ORG_DELETE = "org_delete"
    
    # API Key actions
    API_KEY_CREATE = "api_key_create"
    API_KEY_UPDATE = "api_key_update"
    API_KEY_DELETE = "api_key_delete"
    API_KEY_USE = "api_key_use"
    
    # Test actions
    TEST_CREATE = "test_create"
    TEST_UPDATE = "test_update"
    TEST_DELETE = "test_delete"
    TEST_START = "test_start"
    TEST_STOP = "test_stop"
    TEST_ABORT = "test_abort"
    TEST_SCHEDULE = "test_schedule"
    
    # Subscription actions
    SUBSCRIPTION_CREATE = "subscription_create"
    SUBSCRIPTION_UPDATE = "subscription_update"
    SUBSCRIPTION_CANCEL = "subscription_cancel"
    
    # System actions
    SYSTEM_CONFIG_CHANGE = "system_config_change"
    SYSTEM_BACKUP = "system_backup"
    SYSTEM_RESTORE = "system_restore"
    EMERGENCY_STOP = "emergency_stop"
    
    # Security actions
    SECURITY_BREACH = "security_breach"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"

class AuditSeverity(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    log_id = Column(String(100), unique=True, index=True)  # Unique log identifier
    
    # Action details
    action = Column(SQLEnum(AuditAction), nullable=False)
    action_description = Column(Text)
    severity = Column(SQLEnum(AuditSeverity), default=AuditSeverity.LOW)
    
    # User information
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user_email = Column(String(255))  # Denormalized for performance
    user_role = Column(String(50))
    
    # Organization information
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    organization_name = Column(String(255))
    
    # Resource information
    resource_type = Column(String(50))  # user, test, api_key, etc.
    resource_id = Column(String(100))  # ID of the affected resource
    resource_details = Column(Text)  # JSON string of resource snapshot
    
    # Request information
    ip_address = Column(String(45))  # IPv6 compatible
    user_agent = Column(Text)
    request_method = Column(String(10))
    request_path = Column(String(500))
    request_id = Column(String(100))  # Request tracking ID
    
    # Authentication information
    auth_method = Column(String(50))  # jwt, api_key, oauth, etc.
    api_key_id = Column(String(100))
    
    # Compliance information
    authorization_document_hash = Column(String(255))
    justification = Column(Text)
    compliance_tags = Column(Text)  # JSON array of compliance tags
    
    # Result information
    success = Column(String(10))  # success, failure, partial
    error_message = Column(Text)
    error_code = Column(String(50))
    
    # Timing information
    timestamp = Column(DateTime, default=datetime.utcnow)
    duration_ms = Column(Integer)  # Request duration in milliseconds
    
    # Additional context
    metadata = Column(Text)  # JSON string for additional context
    before_state = Column(Text)  # JSON string of state before action
    after_state = Column(Text)  # JSON string of state after action
    
    # System information
    service_name = Column(String(100))  # Backend service that logged the action
    service_version = Column(String(50))
    instance_id = Column(String(100))
    
    # Immutable flag (for compliance)
    is_immutable = Column(String(10), default="true")  # true, false

class SystemLog(Base):
    __tablename__ = "system_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Log details
    level = Column(String(20))  # DEBUG, INFO, WARN, ERROR, FATAL
    message = Column(Text)
    category = Column(String(50))  # performance, security, error, etc.
    
    # Source information
    service_name = Column(String(100))
    component = Column(String(100))
    function_name = Column(String(100))
    
    # Timing
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Context
    correlation_id = Column(String(100))
    user_id = Column(Integer, nullable=True)
    request_id = Column(String(100))
    
    # Additional data
    metadata = Column(Text)  # JSON string
    stack_trace = Column(Text)
    
    # Performance metrics
    duration_ms = Column(Integer)
    memory_usage = Column(Integer)
    cpu_usage = Column(Float)

# Audit utilities
def create_audit_log(
    action: AuditAction,
    user_id: int = None,
    user_email: str = None,
    organization_id: int = None,
    resource_type: str = None,
    resource_id: str = None,
    ip_address: str = None,
    auth_method: str = None,
    success: str = "success",
    metadata: dict = None,
    severity: AuditSeverity = AuditSeverity.LOW
) -> dict:
    """Create an audit log entry."""
    return {
        "action": action,
        "user_id": user_id,
        "user_email": user_email,
        "organization_id": organization_id,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "ip_address": ip_address,
        "auth_method": auth_method,
        "success": success,
        "metadata": metadata,
        "severity": severity,
        "timestamp": datetime.utcnow()
    }

def generate_log_id() -> str:
    """Generate a unique log ID."""
    import uuid
    return str(uuid.uuid4())