import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

// Custom metrics
export let errorRate = new Rate('errors');

// Test configuration
export let options = {
  // Default configuration (will be overridden by test parameters)
  stages: [
    { duration: '2m', target: 100 }, // ramp up to 100 users
    { duration: '5m', target: 100 }, // stay at 100 users
    { duration: '2m', target: 0 },   // ramp down to 0 users
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'], // 95% of requests should be below 500ms
    http_req_failed: ['rate<0.1'],    // error rate should be below 10%
    errors: ['rate<0.1'],             // custom error rate below 10%
  },
  rps: 100, // requests per second limit
};

// Environment variables that will be set by the backend
const TARGET_URL = __ENV.TARGET_URL || 'http://localhost:8080';
const TARGET_METHOD = __ENV.TARGET_METHOD || 'GET';
const TARGET_HEADERS = __ENV.TARGET_HEADERS || '{}';
const TARGET_BODY = __ENV.TARGET_BODY || '';
const AUTH_TOKEN = __ENV.AUTH_TOKEN || '';
const TEST_DURATION = __ENV.TEST_DURATION || '600s';

// Parse headers from JSON string
let headers = {};
try {
  headers = JSON.parse(TARGET_HEADERS);
} catch (e) {
  console.log('Error parsing headers:', e);
}

// Add authorization header if token is provided
if (AUTH_TOKEN) {
  headers['Authorization'] = `Bearer ${AUTH_TOKEN}`;
}

export default function () {
  // Prepare request parameters
  let params = {
    headers: headers,
  };

  let response;
  
  // Make the request based on method
  switch (TARGET_METHOD.toUpperCase()) {
    case 'GET':
      response = http.get(TARGET_URL, params);
      break;
    case 'POST':
      response = http.post(TARGET_URL, TARGET_BODY, params);
      break;
    case 'PUT':
      response = http.put(TARGET_URL, TARGET_BODY, params);
      break;
    case 'DELETE':
      response = http.del(TARGET_URL, params);
      break;
    case 'PATCH':
      response = http.patch(TARGET_URL, TARGET_BODY, params);
      break;
    default:
      response = http.get(TARGET_URL, params);
  }

  // Check response
  let success = check(response, {
    'status is 200': (r) => r.status === 200,
    'response time < 500ms': (r) => r.timings.duration < 500,
  });

  // Track errors
  errorRate.add(!success);

  // Add custom metrics
  if (!success) {
    console.log(`Request failed: ${response.status} - ${response.body}`);
  }

  // Small delay between requests
  sleep(0.1);
}

// Handle test setup
export function setup() {
  console.log(`Starting load test against: ${TARGET_URL}`);
  console.log(`Method: ${TARGET_METHOD}`);
  console.log(`Duration: ${TEST_DURATION}`);
  console.log(`Headers:`, JSON.stringify(headers, null, 2));
  
  return {
    startTime: new Date().toISOString(),
  };
}

// Handle test teardown
export function teardown(data) {
  console.log('Load test completed');
  console.log(`Start time: ${data.startTime}`);
  console.log(`End time: ${new Date().toISOString()}`);
}