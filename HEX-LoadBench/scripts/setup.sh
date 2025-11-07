#!/bin/bash

# HEX-LoadBench Setup Script
# This script sets up the complete development environment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print banner
echo -e "${BLUE}"
cat banner.txt
echo -e "${NC}"

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
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
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed. Please install Python 3.11+ first."
        exit 1
    fi
    
    # Check Node.js
    if ! command -v node &> /dev/null; then
        print_error "Node.js is not installed. Please install Node.js 18+ first."
        exit 1
    fi
    
    # Check Java
    if ! command -v java &> /dev/null; then
        print_warning "Java is not installed. You'll need Java 17+ for the auth gateway."
    fi
    
    print_status "Prerequisites check completed!"
}

# Create environment file
create_env_file() {
    print_status "Creating environment configuration..."
    
    if [ ! -f .env ]; then
        cat > .env << EOF
# Database Configuration
DATABASE_URL=sqlite:///./hex_loadbench.db

# Authentication
JWT_SECRET=your-super-secret-jwt-key-change-in-production-$(openssl rand -hex 32)
API_KEY_HEADER=X-API-Key

# API Server
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=false

# Redis (for job queue)
REDIS_URL=redis://redis:6379

# Load Testing Configuration
MAX_RPS_PER_TEST=10000
MAX_CONCURRENT_USERS_PER_TEST=1000
DEFAULT_REGION=us-east-1

# Safety Settings
GLOBAL_DAILY_RPS_CAP=10000000
EMERGENCY_KILL_SWITCH=false
RATE_LIMIT_PER_IP=1000

# Email Configuration (optional)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=

# Notification Settings (optional)
TELEGRAM_BOT_TOKEN=
SLACK_WEBHOOK_URL=

# Security
REQUIRE_AUTH_DOCUMENT=true
AUDIT_LOG_RETENTION_DAYS=365
PROMETHEUS_ENABLED=true
EOF
        print_status "Created .env file with default configuration"
        print_warning "Please update the .env file with your specific settings"
    else
        print_warning ".env file already exists, skipping creation"
    fi
}

# Install Python dependencies
install_python_deps() {
    print_status "Installing Python dependencies..."
    
    cd backend
    if [ -f requirements.txt ]; then
        python3 -m venv venv
        source venv/bin/activate
        pip install --upgrade pip
        pip install -r requirements.txt
        print_status "Python dependencies installed"
    else
        print_error "requirements.txt not found in backend directory"
        exit 1
    fi
    cd ..
}

# Install Node.js dependencies
install_node_deps() {
    print_status "Installing Node.js dependencies..."
    
    # Frontend dependencies
    cd frontend
    if [ -f package.json ]; then
        npm install
        print_status "Frontend Node.js dependencies installed"
    else
        print_warning "package.json not found in frontend directory"
    fi
    cd ..
    
    # Job queue dependencies
    cd job-queue
    if [ -f package.json ]; then
        npm install
        print_status "Job queue Node.js dependencies installed"
    else
        print_warning "package.json not found in job-queue directory"
    fi
    cd ..
}

# Build and start services
start_services() {
    print_status "Building and starting services..."
    
    # Build Docker images
    docker-compose build
    
    # Start services
    docker-compose up -d
    
    print_status "Services started in the background"
}

# Wait for services to be ready
wait_for_services() {
    print_status "Waiting for services to be ready..."
    
    # Wait for backend API
    for i in {1..30}; do
        if curl -f http://localhost:8000/health &> /dev/null; then
            print_status "Backend API is ready"
            break
        fi
        if [ $i -eq 30 ]; then
            print_error "Backend API failed to start"
            exit 1
        fi
        sleep 2
    done
    
    # Wait for frontend
    for i in {1..30}; do
        if curl -f http://localhost:3000 &> /dev/null; then
            print_status "Frontend is ready"
            break
        fi
        if [ $i -eq 30 ]; then
            print_error "Frontend failed to start"
            exit 1
        fi
        sleep 2
    done
    
    # Wait for auth gateway
    for i in {1..30}; do
        if curl -f http://localhost:8080/actuator/health &> /dev/null; then
            print_status "Auth gateway is ready"
            break
        fi
        if [ $i -eq 30 ]; then
            print_error "Auth gateway failed to start"
            exit 1
        fi
        sleep 2
    done
}

# Create initial admin user
create_admin_user() {
    print_status "Creating initial admin user..."
    
    # Wait a bit more for the database to be ready
    sleep 5
    
    # Create admin user via API
    curl -X POST http://localhost:8000/api/v1/users/ \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer admin-token" \
        -d '{
            "email": "admin@hexloadbench.com",
            "username": "admin",
            "password": "admin123456",
            "full_name": "System Administrator",
            "role": "admin"
        }' || print_warning "Could not create admin user automatically"
    
    print_status "Admin user creation attempted"
}

# Display setup completion message
show_completion_message() {
    print_status "Setup completed successfully!"
    echo ""
    echo -e "${GREEN}=== HEX-LoadBench is now running ===${NC}"
    echo ""
    echo "Access the platform at the following URLs:"
    echo -e "• Frontend Dashboard: ${BLUE}http://localhost:3000${NC}"
    echo -e "• Backend API:       ${BLUE}http://localhost:8000${NC}"
    echo -e "• API Documentation:  ${BLUE}http://localhost:8000/docs${NC}"
    echo -e "• Auth Gateway:       ${BLUE}http://localhost:8080${NC}"
    echo -e "• Job Queue:          ${BLUE}http://localhost:9000${NC}"
    echo -e "• Prometheus:         ${BLUE}http://localhost:9090${NC}"
    echo -e "• Grafana:            ${BLUE}http://localhost:3001${NC}"
    echo ""
    echo "Default admin credentials:"
    echo -e "• Email:    ${YELLOW}admin@hexloadbench.com${NC}"
    echo -e "• Password: ${YELLOW}admin123456${NC}"
    echo ""
    echo "⚠️  Please change the default password after first login!"
    echo ""
    echo "Useful commands:"
    echo -e "• View logs:     ${BLUE}docker-compose logs -f${NC}"
    echo -e "• Stop services: ${BLUE}docker-compose down${NC}"
    echo -e "• Restart:       ${BLUE}docker-compose restart${NC}"
    echo ""
    echo -e "${GREEN}Happy load testing! 🚀${NC}"
}

# Main setup function
main() {
    print_status "Starting HEX-LoadBench setup..."
    
    check_prerequisites
    create_env_file
    install_python_deps
    install_node_deps
    start_services
    wait_for_services
    create_admin_user
    show_completion_message
}

# Handle script interruption
trap 'print_error "Setup interrupted!"; exit 1' INT TERM

# Run main function
main "$@"