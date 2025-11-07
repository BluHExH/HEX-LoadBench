# HEX-LoadBench - Load-Testing & API Stress Test Platform

⚠️ **THIS TOOL IS FOR AUTHORIZED PERFORMANCE TESTING ONLY.**

![HEX-LoadBench Banner](scripts/banner.txt)

## 🎯 Overview

HEX-LoadBench is a production-ready, multi-tenant load-testing and API stress-test automation platform designed for performance testing, capacity planning, and SLA validation. Built with a microservices architecture supporting multiple programming languages and load testing engines.

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │  Auth Gateway   │    │   Job Queue     │
│  (HTML/CSS/JS)  │◄──►│  (Spring Boot)  │◄──►│   (Node.js)     │
│   Port: 3000    │    │   Port: 8080    │    │   Port: 9000    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Backend API   │    │   Load Runners  │    │   Database      │
│  (FastAPI)      │◄──►│   (k6/Python)   │◄──►│ (SQLite/PG)     │
│   Port: 8000    │    │   Multiple      │    │   Port: 5432    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 18+
- Python 3.11+
- Java 17+ (for auth gateway)
- Go 1.21+ (optional for high-performance runner)

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd HEX-LoadBench
   ```

2. **Display banner (optional):**
   ```bash
   cat scripts/banner.txt
   ```

3. **Run setup script:**
   ```bash
   chmod +x scripts/setup.sh
   ./scripts/setup.sh
   ```

4. **Start all services:**
   ```bash
   docker-compose up -d
   ```

5. **Access the platform:**
   - Frontend Dashboard: http://localhost:3000
   - API Documentation: http://localhost:8000/docs
   - Auth Gateway: http://localhost:8080

## 📋 Features

### 🔐 Multi-Tenant User Management
- User creation with roles (admin, operator, viewer)
- Organization-based access control
- Subscription plans (Free/Basic/Pro/VIP)
- API key issuance with expiration and scopes
- Audit trail for all operations

### 🎯 Load Testing Capabilities
- **Multiple Load Profiles:**
  - Ramp-up: Gradual increase in load
  - Steady-state: Constant load testing
  - Spike: Sudden load spikes
  - Soak: Extended duration testing
- **Multiple Engines:**
  - k6 integration for high-performance tests
  - Python asyncio runner (httpx/aiohttp)
  - Optional Go microservice for extreme concurrency
- **Real-time Telemetry:**
  - Latency metrics (P50/P95/P99)
  - Throughput and error rates
  - Live dashboard updates via WebSocket

### 🛡️ Safety & Compliance
- Per-organization and global rate limits
- Emergency kill switch
- Authorization document validation
- Immutable audit logging
- GDPR compliance features

### 📊 Monitoring & Reporting
- Real-time dashboards with live metrics
- Exportable reports (CSV, JSON, PDF)
- Prometheus metrics endpoint
- Email, Slack, and Telegram notifications

## 🔧 Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

```bash
# Database
DATABASE_URL=sqlite:///./hex_loadbench.db

# Authentication
JWT_SECRET=your-super-secret-key
API_KEY_HEADER=X-API-Key

# Load Testing
MAX_RPS_PER_TEST=10000
MAX_CONCURRENT_USERS=1000

# Notifications
TELEGRAM_BOT_TOKEN=your_token
SLACK_WEBHOOK_URL=your_webhook
```

### Test Configuration

Create a test definition file:

```yaml
# test-config.yaml
test_name: "API Load Test"
target_url: "https://api.example.com/users"
method: "GET"
headers:
  Authorization: "Bearer {{token}}"
load_profile:
  type: "ramp_up"
  initial_users: 10
  target_users: 100
  duration: 300
limits:
  max_rps: 500
  max_errors: 5
schedule:
  cron: "0 2 * * *"  # Daily at 2 AM
notifications:
  on_start: true
  on_complete: true
  channels: ["email", "slack"]
```

## 🎮 Usage Examples

### CLI Usage

```bash
# Create a new test
./bin/hexloadbench create-test --config test-config.yaml

# Run a test immediately
./bin/hexloadbench run-test --test-id 123

# Schedule a test
./bin/hexloadbench schedule-test --test-id 123 --cron "0 2 * * *"

# Get test results
./bin/hexloadbench get-report --test-id 123 --format json

# Abort a running test
./bin/hexloadbench abort-test --test-id 123
```

### API Usage

```bash
# Authenticate
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "password"}'

# Create test
curl -X POST "http://localhost:8000/api/v1/tests" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d @test-config.json

# Start test
curl -X POST "http://localhost:8000/api/v1/tests/123/start" \
  -H "Authorization: Bearer <token>"

# Get results
curl -X GET "http://localhost:8000/api/v1/tests/123/results" \
  -H "Authorization: Bearer <token>"
```

## 📱 Termux Usage

For Android/Termux users:

```bash
# Install required packages
pkg install python nodejs git docker

# Clone and setup
git clone <repository-url>
cd HEX-LoadBench
cat scripts/banner.txt

# Run lightweight setup (SQLite + Python runner only)
./scripts/setup_termux.sh
```

## 🔍 API Documentation

OpenAPI/Swagger documentation is available at:
- **Interactive UI:** http://localhost:8000/docs
- **JSON Spec:** http://localhost:8000/openapi.json

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/login` | User authentication |
| GET | `/users/me` | Current user info |
| POST | `/tests` | Create test definition |
| POST | `/tests/{id}/start` | Start a test |
| POST | `/tests/{id}/abort` | Abort running test |
| GET | `/tests/{id}/results` | Get test results |
| GET | `/reports/{id}` | Download report |

## 🏗️ Development

### Local Development Setup

1. **Backend (Python/FastAPI):**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```

2. **Frontend:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

3. **Auth Gateway (Java):**
   ```bash
   cd auth-gateway
   ./mvnw spring-boot:run
   ```

4. **Job Queue (Node.js):**
   ```bash
   cd job-queue
   npm install
   npm start
   ```

### Running Tests

```bash
# Backend tests
cd backend && python -m pytest

# Integration tests
cd tests/integration && python run_tests.py

# Load tests (using platform itself)
./scripts/self_test.sh
```

## 🐳 Docker Deployment

### Production Deployment

```bash
# Build and deploy
docker-compose -f docker-compose.prod.yml up -d

# Scale services
docker-compose -f docker-compose.prod.yml up -d --scale backend=3

# View logs
docker-compose logs -f
```

### Kubernetes Deployment

```bash
# Install Helm chart
helm install hex-loadbench k8s/helm/hex-loadbench

# Upgrade
helm upgrade hex-loadbench k8s/helm/hex-loadbench
```

## 🔐 Security Considerations

- **Authentication:** JWT tokens + API keys
- **Authorization:** Role-based access control (RBAC)
- **Audit Logging:** Immutable logs for compliance
- **Rate Limiting:** Per-user and global limits
- **Network Security:** TLS encryption everywhere
- **Data Protection:** GDPR-compliant data handling

## 📊 Monitoring & Observability

### Metrics

- **Prometheus:** `/metrics` endpoint
- **Health Checks:** `/health` endpoint
- **Custom Metrics:** Test execution, user activity, system load

### Logging

- **Structured Logs:** JSON format for easy parsing
- **Log Levels:** DEBUG, INFO, WARN, ERROR
- **Audit Trail:** Separate audit log for compliance

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Legal Disclaimer

**THIS TOOL IS FOR AUTHORIZED PERFORMANCE TESTING ONLY.**

Users are responsible for ensuring they have proper authorization before testing any systems. Unauthorized testing may violate laws and terms of service. The authors assume no liability for misuse.

## 📞 Support

- **Documentation:** Check the `/docs` folder
- **Issues:** Open an issue on GitHub
- **Security:** Report security issues to security@hexloadbench.com

## 🗺️ Roadmap

- [ ] GraphQL API support
- [ ] Advanced report customization
- [ ] Multi-cloud runner support
- [ ] Machine learning-based anomaly detection
- [ ] Advanced correlation analysis
- [ ] CI/CD integrations (Jenkins, GitLab CI)
- [ ] Advanced security scanning integration

---

**HEX-LoadBench** - Professional Load Testing Made Simple 🚀
