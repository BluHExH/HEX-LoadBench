#!/bin/bash

# HEX-LoadBench Termux Setup Script
# Lightweight setup for Android/Termux environments

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

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check Termux environment
check_termux() {
    print_status "Checking Termux environment..."
    
    if [ ! -d "/data/data/com.termux/files/usr" ]; then
        print_error "This script must be run in Termux environment"
        exit 1
    fi
    
    print_status "Termux environment verified"
}

# Update packages
update_packages() {
    print_status "Updating Termux packages..."
    
    pkg update -y
    pkg upgrade -y
    
    print_status "Packages updated"
}

# Install prerequisites
install_prerequisites() {
    print_status "Installing prerequisites..."
    
    # Core packages
    pkg install -y python curl git wget sqlite nginx
    
    # Python packages
    pip install --upgrade pip
    
    print_status "Prerequisites installed"
}

# Install k6 (if possible)
install_k6() {
    print_status "Attempting to install k6..."
    
    # Try to download k6 binary
    K6_VERSION="0.47.0"
    ARCH="arm64"
    
    if curl -L "https://github.com/grafana/k6/releases/download/v${K6_VERSION}/k6-v${K6_VERSION}-linux-${ARCH}.tar.gz" -o k6.tar.gz; then
        tar -xzf k6.tar.gz
        cp k6-v${K6_VERSION}-linux-${ARCH}/k6 $PREFIX/bin/
        chmod +x $PREFIX/bin/k6
        rm -rf k6.tar.gz k6-v${K6_VERSION}-linux-${ARCH}
        print_status "k6 installed successfully"
    else
        print_warning "Could not install k6, will use Python runner instead"
    fi
}

# Setup Python environment
setup_python_env() {
    print_status "Setting up Python environment..."
    
    cd backend
    
    # Create virtual environment
    python -m venv venv
    source venv/bin/activate
    
    # Install dependencies
    pip install --upgrade pip
    pip install fastapi uvicorn sqlalchemy alembic pydantic python-jose passlib python-multipart redis httpx aiohttp prometheus-client structlog python-dotenv pytest pytest-asyncio
    
    print_status "Python environment setup completed"
    cd ..
}

# Create lightweight configuration
create_lightweight_config() {
    print_status "Creating lightweight configuration..."
    
    # Create minimal config for Termux
    cat > config/config_termux.yaml << EOF
organization: "HEX-LoadBench Termux"
version: "1.0.0"
setupDate: "$(date -Iseconds)"

# Database Configuration
database:
  type: "sqlite"
  connection: "sqlite:///./hex_loadbench_termux.db"

# API Server Configuration
api_server:
  host: "0.0.0.0"
  port: 8000
  debug: true
  cors_origins: ["*"]

# Load Testing Configuration
load_testing:
  default_timeout: 300
  max_rps_per_test: 1000  # Reduced for Termux
  max_concurrent_users_per_test: 50  # Reduced for Termux
  regions: ["local"]

# Subscription Plans (simplified for Termux)
plans:
  free:
    name: "Free"
    max_daily_rps: 1000
    max_concurrent_tests: 1
    max_test_duration: 600
  basic:
    name: "Basic"
    max_daily_rps: 5000
    max_concurrent_tests: 2
    max_test_duration: 1800

# Safety Limits
safety:
  global_daily_rps_cap: 100000
  emergency_kill_switch: false
  rate_limit_per_ip: 100

# Audit & Compliance
audit:
  log_retention_days: 30
  immutable_logs: true
  require_auth_document: false  # Disabled for Termux
EOF
    
    print_status "Lightweight configuration created"
}

# Create startup script
create_startup_script() {
    print_status "Creating startup script..."
    
    cat > start_termux.sh << 'EOF'
#!/bin/bash

# HEX-LoadBench Termux Startup Script

echo "Starting HEX-LoadBench on Termux..."

# Activate Python virtual environment
cd backend
source venv/bin/activate

# Start the backend API
echo "Starting backend API on port 8000..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Wait for backend to start
sleep 5

# Start frontend with simple HTTP server
echo "Starting frontend on port 3000..."
cd ../frontend
python -m http.server 3000 &
FRONTEND_PID=$!

echo ""
echo "=== HEX-LoadBench is running ==="
echo "Frontend: http://localhost:3000"
echo "Backend API: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Wait for interrupt
trap "echo 'Stopping services...'; kill $BACKEND_PID $FRONTEND_PID; exit" INT TERM

wait
EOF
    
    chmod +x start_termux.sh
    print_status "Startup script created"
}

# Create Termux service
create_termux_service() {
    print_status "Creating Termux service..."
    
    # Create termux service directory
    mkdir -p ~/.termux/boot
    
    cat > ~/.termux/boot/hex-loadbench.sh << 'EOF'
#!/bin/bash

# HEX-LoadBench Termux Boot Service

cd /data/data/com.termux/files/home/HEX-LoadBench
./start_termux.sh
EOF
    
    chmod +x ~/.termux/boot/hex-loadbench.sh
    
    print_warning "Boot service created. Enable with: termux-boot start"
}

# Create demo test
create_demo_test() {
    print_status "Creating demo test..."
    
    cat > demo_test.json << EOF
{
  "name": "Termux Demo Test",
  "description": "Simple demo test for Termux environment",
  "target_url": "http://localhost:8000/health",
  "method": "GET",
  "load_profile_type": "steady_state",
  "load_profile_config": {
    "concurrent_users": 10,
    "duration": 60
  },
  "duration": 60,
  "max_concurrent_users": 10,
  "rps_limit": 50,
  "timeout": 30,
  "region": "local",
  "use_proxies": false
}
EOF
    
    print_status "Demo test configuration created"
}

# Display completion message
show_completion_message() {
    print_status "Termux setup completed successfully!"
    echo ""
    echo -e "${GREEN}=== HEX-LoadBench Termux is ready ===${NC}"
    echo ""
    echo "To start the platform:"
    echo -e "${BLUE}./start_termux.sh${NC}"
    echo ""
    echo "Access URLs:"
    echo -e "• Frontend: ${BLUE}http://localhost:3000${NC}"
    echo -e "• Backend API: ${BLUE}http://localhost:8000${NC}"
    echo -e "• API Documentation: ${BLUE}http://localhost:8000/docs${NC}"
    echo ""
    echo "Demo test configuration:"
    echo -e "• File: ${BLUE}demo_test.json${NC}"
    echo ""
    echo "Termux-specific notes:"
    echo "• Reduced resource limits for mobile devices"
    echo "• SQLite database for simplicity"
    echo "• Python runner as primary engine"
    echo "• No authentication requirement for local testing"
    echo ""
    echo -e "${GREEN}Happy mobile load testing! 📱${NC}"
}

# Main setup function
main() {
    print_status "Starting HEX-LoadBench Termux setup..."
    
    check_termux
    update_packages
    install_prerequisites
    install_k6
    setup_python_env
    create_lightweight_config
    create_startup_script
    create_termux_service
    create_demo_test
    show_completion_message
}

# Handle script interruption
trap 'print_error "Setup interrupted!"; exit 1' INT TERM

# Run main function
main "$@"