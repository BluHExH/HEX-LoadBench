#!/bin/bash

# HEX-LoadBench Docker Deployment Script
# Production-ready deployment using Docker and Docker Compose

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="hex-loadbench"
COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.prod"

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Print banner
echo -e "${BLUE}"
cat banner.txt
echo -e "${NC}"
echo -e "${BLUE}Production Docker Deployment${NC}"
echo ""

# Check if running as root (not recommended)
check_root_user() {
    if [ "$EUID" -eq 0 ]; then
        print_warning "Running as root is not recommended. Consider creating a dedicated user."
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Check prerequisites
check_prerequisites() {
    print_status "Checking deployment prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    # Check if we can connect to Docker
    if ! docker info &> /dev/null; then
        print_error "Cannot connect to Docker daemon. Please check your Docker installation."
        exit 1
    fi
    
    # Check available disk space (minimum 2GB)
    available_space=$(df . | tail -1 | awk '{print $4}')
    if [ "$available_space" -lt 2097152 ]; then
        print_warning "Low disk space detected. Recommended: 2GB+ free space."
    fi
    
    print_status "Prerequisites check completed"
}

# Create production environment file
create_production_env() {
    print_status "Creating production environment configuration..."
    
    if [ ! -f "$ENV_FILE" ]; then
        cat > "$ENV_FILE" << EOF
# ===========================================
# HEX-LoadBench Production Configuration
# ===========================================

# Database Configuration
DATABASE_URL=postgresql://hexuser:$(openssl rand -base64 32)@postgres:5432/hex_loadbench

# Authentication Security
JWT_SECRET=$(openssl rand -hex 64)
API_KEY_HEADER=X-API-Key
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Redis Configuration
REDIS_URL=redis://redis:6379

# API Server Configuration
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=false
CORS_ORIGINS=["https://yourdomain.com"]

# Load Testing Limits
MAX_RPS_PER_TEST=10000
MAX_CONCURRENT_USERS_PER_TEST=1000
DEFAULT_REGION=us-east-1

# Safety and Security
GLOBAL_DAILY_RPS_CAP=10000000
EMERGENCY_KILL_SWITCH=false
RATE_LIMIT_PER_IP=1000
ALLOWED_TARGET_DOMAINS=[]

# Email Configuration (required for production)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=noreply@yourdomain.com

# Notification Configuration
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK

# Security Settings
REQUIRE_AUTH_DOCUMENT=true
AUDIT_LOG_RETENTION_DAYS=365
IMMUTABLE_AUDIT_LOGS=true
PROMETHEUS_ENABLED=true

# SSL/TLS Configuration
SSL_CERT_PATH=/etc/nginx/ssl/cert.pem
SSL_KEY_PATH=/etc/nginx/ssl/key.pem

# Monitoring
GRAFANA_ADMIN_PASSWORD=$(openssl rand -base64 16)
EOF
        print_status "Created $ENV_FILE with secure defaults"
        print_warning "Please update the $ENV_FILE with your production values"
        print_warning "特别注意: Update SMTP credentials, domain names, and SSL certificates"
    else
        print_warning "$ENV_FILE already exists, skipping creation"
    fi
}

# Create production docker-compose file
create_production_compose() {
    print_status "Creating production Docker Compose configuration..."
    
    if [ ! -f "$COMPOSE_FILE" ]; then
        cat > "$COMPOSE_FILE" << 'EOF'
version: '3.8'

services:
  # PostgreSQL Database
  postgres:
    image: postgres:15
    container_name: ${PROJECT_NAME}-db
    environment:
      POSTGRES_DB: hex_loadbench
      POSTGRES_USER: hexuser
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backend/migrations:/docker-entrypoint-initdb.d
    networks:
      - hex-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U hexuser -d hex_loadbench"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Redis for Job Queue
  redis:
    image: redis:7-alpine
    container_name: ${PROJECT_NAME}-redis
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    networks:
      - hex-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  # Backend API (Python/FastAPI)
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: ${PROJECT_NAME}-backend
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - JWT_SECRET=${JWT_SECRET}
      - API_HOST=0.0.0.0
      - API_PORT=8000
      - DEBUG=false
    volumes:
      - ./config:/app/config:ro
      - ./runner:/app/runner:ro
      - ./logs:/app/logs
    networks:
      - hex-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  # Auth Gateway (Java/Spring Boot)
  auth-gateway:
    build:
      context: ./auth-gateway
      dockerfile: Dockerfile
    container_name: ${PROJECT_NAME}-auth
    environment:
      - SPRING_PROFILES_ACTIVE=docker,production
      - DATABASE_URL=${DATABASE_URL}
      - JWT_SECRET=${JWT_SECRET}
      - API_BACKEND_URL=http://backend:8000
    networks:
      - hex-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/actuator/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    depends_on:
      postgres:
        condition: service_healthy
      backend:
        condition: service_healthy

  # Job Queue Service (Node.js)
  job-queue:
    build:
      context: ./job-queue
      dockerfile: Dockerfile
    container_name: ${PROJECT_NAME}-jobqueue
    environment:
      - NODE_ENV=production
      - REDIS_URL=${REDIS_URL}
      - API_BACKEND_URL=http://backend:8000
      - AUTH_GATEWAY_URL=http://auth-gateway:8080
    volumes:
      - ./runner:/app/runner:ro
      - ./config:/app/config:ro
      - ./logs:/app/logs
    networks:
      - hex-network
    restart: unless-stopped
    depends_on:
      redis:
        condition: service_healthy
      backend:
        condition: service_healthy

  # Frontend Dashboard
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: ${PROJECT_NAME}-frontend
    volumes:
      - ./docker/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    networks:
      - hex-network
    restart: unless-stopped
    depends_on:
      - backend
      - auth-gateway

  # Nginx Reverse Proxy
  nginx:
    image: nginx:alpine
    container_name: ${PROJECT_NAME}-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./docker/nginx.prod.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
      - ./logs/nginx:/var/log/nginx
    networks:
      - hex-network
    restart: unless-stopped
    depends_on:
      - frontend
      - backend
      - auth-gateway

  # Prometheus for Monitoring
  prometheus:
    image: prom/prometheus:latest
    container_name: ${PROJECT_NAME}-prometheus
    volumes:
      - ./docker/prometheus.prod.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
      - ./ssl:/etc/ssl/certs:ro
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--storage.tsdb.retention.time=30d'
      - '--web.enable-lifecycle'
    networks:
      - hex-network
    restart: unless-stopped

  # Grafana for Dashboards
  grafana:
    image: grafana/grafana:latest
    container_name: ${PROJECT_NAME}-grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD}
      - GF_SERVER_DOMAIN=${GRAFANA_DOMAIN}
      - GF_SERVER_ROOT_URL=https://${GRAFANA_DOMAIN}/
      - GF_DATABASE_TYPE=postgres
      - GF_DATABASE_HOST=postgres:5432
      - GF_DATABASE_NAME=grafana
      - GF_DATABASE_USER=grafana
      - GF_DATABASE_PASSWORD=${GRAFANA_DB_PASSWORD}
    volumes:
      - grafana_data:/var/lib/grafana
      - ./docker/grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
      - ./docker/grafana/datasources:/etc/grafana/provisioning/datasources:ro
      - ./ssl:/etc/ssl/certs:ro
    networks:
      - hex-network
    restart: unless-stopped
    depends_on:
      - prometheus
      - postgres

volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local
  prometheus_data:
    driver: local
  grafana_data:
    driver: local

networks:
  hex-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
EOF
        print_status "Created $COMPOSE_FILE with production configuration"
    else
        print_warning "$COMPOSE_FILE already exists, skipping creation"
    fi
}

# Create SSL directory and generate self-signed certificate
setup_ssl() {
    print_status "Setting up SSL certificates..."
    
    mkdir -p ssl
    
    if [ ! -f "ssl/cert.pem" ] || [ ! -f "ssl/key.pem" ]; then
        print_warning "Generating self-signed SSL certificate (for testing only)"
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout ssl/key.pem \
            -out ssl/cert.pem \
            -subj "/C=US/ST=State/L=City/O=HEX-LoadBench/CN=localhost"
        print_status "Self-signed certificate generated"
        print_warning "For production, replace with proper CA-signed certificates"
    else
        print_status "SSL certificates already exist"
    fi
}

# Create necessary directories
create_directories() {
    print_status "Creating necessary directories..."
    
    mkdir -p logs/{backend,auth,jobqueue,nginx}
    mkdir -p backups
    mkdir -p ssl
    
    # Set proper permissions
    chmod 755 logs
    chmod 700 ssl
    
    print_status "Directories created"
}

# Build and deploy services
deploy_services() {
    print_status "Building and deploying services..."
    
    # Load environment variables
    source $ENV_FILE
    
    # Build images
    print_status "Building Docker images..."
    docker-compose -f $COMPOSE_FILE build --no-cache
    
    # Start services
    print_status "Starting services..."
    docker-compose -f $COMPOSE_FILE up -d
    
    print_status "Services deployed"
}

# Wait for services to be healthy
wait_for_services() {
    print_status "Waiting for services to be healthy..."
    
    # Wait up to 5 minutes for services
    for i in {1..30}; do
        healthy_count=$(docker-compose -f $COMPOSE_FILE ps --services --filter "status=running" | wc -l)
        total_count=$(docker-compose -f $COMPOSE_FILE config --services | wc -l)
        
        echo "Progress: $healthy_count/$total_count services healthy"
        
        if [ "$healthy_count" -eq "$total_count" ]; then
            print_status "All services are healthy!"
            break
        fi
        
        if [ $i -eq 30 ]; then
            print_error "Some services failed to start within timeout"
            print_status "Checking service status:"
            docker-compose -f $COMPOSE_FILE ps
            exit 1
        fi
        
        sleep 10
    done
}

# Create admin user
create_admin_user() {
    print_status "Creating initial admin user..."
    
    # Wait for backend to be ready
    sleep 10
    
    # Get admin token (simplified for production)
    ADMIN_TOKEN=$(docker exec ${PROJECT_NAME}-backend python -c "
import sys
sys.path.append('/app')
from app.core.auth import create_access_token
print(create_access_token(data={'sub': '1'}))
")
    
    # Create admin user
    curl -X POST http://localhost:8000/api/v1/users/ \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $ADMIN_TOKEN" \
        -d '{
            "email": "admin@yourdomain.com",
            "username": "admin",
            "password": "change-me-production-password",
            "full_name": "System Administrator",
            "role": "admin"
        }' || print_warning "Could not create admin user automatically"
    
    print_status "Admin user creation attempted"
}

# Run security checks
run_security_checks() {
    print_status "Running security checks..."
    
    # Check for exposed ports
    exposed_ports=$(docker-compose -f $COMPOSE_FILE ps --format "{{.Ports}}" | grep -o "0.0.0.0:[0-9]*" | sort -u)
    print_status "Exposed ports: $exposed_ports"
    
    # Check for running containers as root
    root_containers=$(docker-compose -f $COMPOSE_FILE ps --format "{{.Names}}" | xargs -I {} docker inspect {} --format "{{.Name}}: {{.HostConfig.User}}")
    echo "Container users:"
    echo "$root_containers"
    
    print_status "Security checks completed"
}

# Display deployment information
show_deployment_info() {
    print_status "Deployment completed successfully!"
    echo ""
    echo -e "${GREEN}=== HEX-LoadBench Production Deployment ===${NC}"
    echo ""
    echo "Service URLs:"
    echo -e "• Main Application: ${BLUE}https://yourdomain.com${NC}"
    echo -e "• Backend API:      ${BLUE}https://yourdomain.com/api${NC}"
    echo -e "• Grafana:          ${BLUE}https://grafana.yourdomain.com${NC}"
    echo ""
    echo "Management Commands:"
    echo -e "• View logs:        ${BLUE}docker-compose -f $COMPOSE_FILE logs -f${NC}"
    echo -e "• Check status:     ${BLUE}docker-compose -f $COMPOSE_FILE ps${NC}"
    echo -e "• Stop services:    ${BLUE}docker-compose -f $COMPOSE_FILE down${NC}"
    echo -e "• Update services:  ${BLUE}docker-compose -f $COMPOSE_FILE pull && docker-compose -f $COMPOSE_FILE up -d${NC}"
    echo ""
    echo "Security Reminders:"
    echo -e "• ${YELLOW}Change default admin password${NC}"
    echo -e "• ${YELLOW}Update SMTP credentials${NC}"
    echo -e "• ${YELLOW}Configure proper SSL certificates${NC}"
    echo -e "• ${YELLOW}Set up backup procedures${NC}"
    echo -e "• ${YELLOW}Configure monitoring alerts${NC}"
    echo ""
    echo -e "${GREEN}Production deployment ready! 🔒${NC}"
}

# Main deployment function
main() {
    print_status "Starting HEX-LoadBench production deployment..."
    
    check_root_user
    check_prerequisites
    create_production_env
    create_production_compose
    setup_ssl
    create_directories
    deploy_services
    wait_for_services
    create_admin_user
    run_security_checks
    show_deployment_info
}

# Handle script interruption
trap 'print_error "Deployment interrupted!"; exit 1' INT TERM

# Run main function
main "$@"