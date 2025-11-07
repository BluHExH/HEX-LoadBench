"""
Python-based load runner using asyncio and httpx for lightweight load testing.
Provides an alternative to k6 for smaller scale tests or when k6 is not available.
"""

import asyncio
import httpx
import json
import time
import statistics
import signal
import sys
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class LoadTestConfig:
    """Configuration for load test."""
    target_url: str
    method: str = "GET"
    headers: Dict[str, str] = None
    body: str = ""
    auth_token: str = ""
    concurrent_users: int = 10
    duration: int = 60
    max_rps: int = 100
    timeout: int = 30
    
    def __post_init__(self):
        if self.headers is None:
            self.headers = {}
        if self.auth_token:
            self.headers["Authorization"] = f"Bearer {self.auth_token}"

@dataclass
class TestMetrics:
    """Metrics collected during test execution."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    response_times: List[float] = None
    status_codes: Dict[int, int] = None
    errors: List[str] = None
    start_time: datetime = None
    end_time: datetime = None
    
    def __post_init__(self):
        if self.response_times is None:
            self.response_times = []
        if self.status_codes is None:
            self.status_codes = {}
        if self.errors is None:
            self.errors = []

class LoadRunner:
    """Async load testing runner."""
    
    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.metrics = TestMetrics()
        self.running = False
        self.client = None
        
        # Rate limiting
        self.request_interval = 1.0 / config.max_rps if config.max_rps > 0 else 0.1
        self.last_request_time = 0
        
    async def __aenter__(self):
        """Async context manager entry."""
        self.client = httpx.AsyncClient(
            timeout=self.config.timeout,
            limits=httpx.Limits(max_keepalive_connections=100, max_connections=200)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.client:
            await self.client.aclose()
    
    async def make_request(self) -> Dict[str, Any]:
        """Make a single HTTP request."""
        start_time = time.time()
        
        # Rate limiting
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.request_interval:
            await asyncio.sleep(self.request_interval - time_since_last)
        
        try:
            # Make request based on method
            if self.config.method.upper() == "GET":
                response = await self.client.get(self.config.target_url, headers=self.config.headers)
            elif self.config.method.upper() == "POST":
                response = await self.client.post(
                    self.config.target_url, 
                    data=self.config.body, 
                    headers=self.config.headers
                )
            elif self.config.method.upper() == "PUT":
                response = await self.client.put(
                    self.config.target_url, 
                    data=self.config.body, 
                    headers=self.config.headers
                )
            elif self.config.method.upper() == "DELETE":
                response = await self.client.delete(self.config.target_url, headers=self.config.headers)
            elif self.config.method.upper() == "PATCH":
                response = await self.client.patch(
                    self.config.target_url, 
                    data=self.config.body, 
                    headers=self.config.headers
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {self.config.method}")
            
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            # Record metrics
            self.metrics.total_requests += 1
            self.metrics.response_times.append(response_time)
            
            # Track status codes
            status_code = response.status_code
            self.metrics.status_codes[status_code] = self.metrics.status_codes.get(status_code, 0) + 1
            
            if 200 <= status_code < 300:
                self.metrics.successful_requests += 1
                success = True
            else:
                self.metrics.failed_requests += 1
                success = False
                self.metrics.errors.append(f"HTTP {status_code}: {response.text[:100]}")
            
            self.last_request_time = time.time()
            
            return {
                "success": success,
                "status_code": status_code,
                "response_time": response_time,
                "response_text": response.text[:100] if not success else ""
            }
            
        except httpx.RequestError as e:
            response_time = (time.time() - start_time) * 1000
            self.metrics.total_requests += 1
            self.metrics.failed_requests += 1
            self.metrics.response_times.append(response_time)
            self.metrics.errors.append(f"Request error: {str(e)}")
            
            return {
                "success": False,
                "error": str(e),
                "response_time": response_time
            }
    
    async def run_user_simulation(self, user_id: int):
        """Simulate a single user making requests."""
        logger.info(f"User {user_id} starting simulation")
        
        end_time = time.time() + self.config.duration
        
        while self.running and time.time() < end_time:
            result = await self.make_request()
            
            # Log progress periodically
            if self.metrics.total_requests % 100 == 0:
                logger.info(f"User {user_id}: {self.metrics.total_requests} requests completed")
        
        logger.info(f"User {user_id} simulation completed")
    
    async def run_test(self) -> TestMetrics:
        """Run the complete load test."""
        logger.info(f"Starting load test: {self.config.concurrent_users} users, {self.config.duration}s duration")
        
        self.running = True
        self.metrics.start_time = datetime.utcnow()
        
        try:
            # Create user simulation tasks
            tasks = []
            for user_id in range(self.config.concurrent_users):
                task = asyncio.create_task(self.run_user_simulation(user_id))
                tasks.append(task)
            
            # Wait for all tasks to complete
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            logger.error(f"Load test error: {e}")
            self.metrics.errors.append(f"Test error: {str(e)}")
        
        finally:
            self.running = False
            self.metrics.end_time = datetime.utcnow()
        
        logger.info(f"Load test completed: {self.metrics.total_requests} total requests")
        return self.metrics
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate detailed test report."""
        if not self.metrics.response_times:
            return {"error": "No metrics collected"}
        
        # Calculate statistics
        response_times = self.metrics.response_times
        avg_response_time = statistics.mean(response_times)
        min_response_time = min(response_times)
        max_response_time = max(response_times)
        
        # Percentiles
        sorted_times = sorted(response_times)
        p50 = sorted_times[int(len(sorted_times) * 0.5)]
        p95 = sorted_times[int(len(sorted_times) * 0.95)]
        p99 = sorted_times[int(len(sorted_times) * 0.99)]
        
        # Calculate test duration
        duration = 0
        if self.metrics.start_time and self.metrics.end_time:
            duration = (self.metrics.end_time - self.metrics.start_time).total_seconds()
        
        # Calculate throughput
        throughput = self.metrics.total_requests / duration if duration > 0 else 0
        error_rate = (self.metrics.failed_requests / self.metrics.total_requests * 100) if self.metrics.total_requests > 0 else 0
        
        return {
            "test_config": {
                "target_url": self.config.target_url,
                "method": self.config.method,
                "concurrent_users": self.config.concurrent_users,
                "duration": self.config.duration,
                "max_rps": self.config.max_rps
            },
            "execution": {
                "start_time": self.metrics.start_time.isoformat() if self.metrics.start_time else None,
                "end_time": self.metrics.end_time.isoformat() if self.metrics.end_time else None,
                "duration_seconds": duration
            },
            "metrics": {
                "total_requests": self.metrics.total_requests,
                "successful_requests": self.metrics.successful_requests,
                "failed_requests": self.metrics.failed_requests,
                "error_rate_percent": round(error_rate, 2),
                "throughput_rps": round(throughput, 2)
            },
            "response_times": {
                "average_ms": round(avg_response_time, 2),
                "minimum_ms": round(min_response_time, 2),
                "maximum_ms": round(max_response_time, 2),
                "p50_ms": round(p50, 2),
                "p95_ms": round(p95, 2),
                "p99_ms": round(p99, 2)
            },
            "status_codes": self.metrics.status_codes,
            "errors": self.metrics.errors[:10],  # Limit error output
            "errors_count": len(self.metrics.errors)
        }

# Signal handler for graceful shutdown
def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info("Received shutdown signal, stopping test...")
    sys.exit(0)

async def main():
    """Main function for standalone execution."""
    # Example usage
    config = LoadTestConfig(
        target_url="http://localhost:8080/api/health",
        method="GET",
        concurrent_users=10,
        duration=30,
        max_rps=50
    )
    
    async with LoadRunner(config) as runner:
        metrics = await runner.run_test()
        report = runner.generate_report()
        
        print(json.dumps(report, indent=2))

if __name__ == "__main__":
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run the test
    asyncio.run(main())