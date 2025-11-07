import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

// Custom metrics
export let errorRate = new Rate('errors');
export let responseTime = new Rate('response_times');

// Test configuration from environment variables
const TARGET_URL = __ENV.TARGET_URL || 'http://localhost:8080';
const TARGET_METHOD = __ENV.TARGET_METHOD || 'GET';
const TARGET_HEADERS = __ENV.TARGET_HEADERS || '{}';
const TARGET_BODY = __ENV.TARGET_BODY || '';
const AUTH_TOKEN = __ENV.AUTH_TOKEN || '';
const INITIAL_USERS = parseInt(__ENV.INITIAL_USERS) || 1;
const TARGET_USERS = parseInt(__ENV.TARGET_USERS) || 100;
const RAMP_DURATION = parseInt(__ENV.RAMP_DURATION) || 300; // seconds
const HOLD_DURATION = parseInt(__ENV.HOLD_DURATION) || 600; // seconds
const MAX_RPS = parseInt(__ENV.MAX_RPS) || 1000;

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

// Configure test stages for ramp-up
export let options = {
  stages: [
    { duration: '5s', target: INITIAL_USERS },          // initial users
    { duration: `${RAMP_DURATION}s`, target: TARGET_USERS }, // ramp up
    { duration: `${HOLD_DURATION}s`, target: TARGET_USERS }, // hold at peak
    { duration: '60s', target: 0 },                     // ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<1000'], // 95% below 1s during ramp-up
    http_req_failed: ['rate<0.1'],     // error rate below 10%
    errors: ['rate<0.1'],              // custom error rate below 10%
  },
  rps: MAX_RPS,
};

export default function () {
  // Prepare request parameters
  let params = {
    headers: headers,
  };

  // Make request
  let response;
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

  // Check response with ramp-up specific thresholds
  let success = check(response, {
    'status is 200': (r) => r.status === 200,
    'response time < 1000ms': (r) => r.timings.duration < 1000,
    'response time < 2000ms': (r) => r.timings.duration < 2000,
  });

  // Track errors and response times
  errorRate.add(!success);
  responseTime.add(response.timings.duration);

  // Log detailed metrics during ramp-up
  if (__ENV.VU % 10 === 0) { // Log every 10th virtual user
    console.log(`VU ${__ENV.VU}: ${response.status} - ${response.timings.duration.toFixed(2)}ms`);
  }

  // Adaptive delay based on current response times
  if (response.timings.duration > 500) {
    sleep(0.2); // Longer delay if responses are slow
  } else {
    sleep(0.1); // Normal delay
  }
}

export function setup() {
  console.log(`=== RAMP-UP LOAD TEST ===`);
  console.log(`Target: ${TARGET_URL}`);
  console.log(`Method: ${TARGET_METHOD}`);
  console.log(`Users: ${INITIAL_USERS} → ${TARGET_USERS}`);
  console.log(`Ramp duration: ${RAMP_DURATION}s`);
  console.log(`Hold duration: ${HOLD_DURATION}s`);
  console.log(`Max RPS: ${MAX_RPS}`);
  console.log(`========================`);
  
  return {
    startTime: new Date().toISOString(),
    initialUsers: INITIAL_USERS,
    targetUsers: TARGET_USERS,
  };
}

export function teardown(data) {
  console.log('=== RAMP-UP TEST COMPLETED ===');
  console.log(`Start time: ${data.startTime}`);
  console.log(`End time: ${new Date().toISOString()}`);
  console.log(`User range: ${data.initialUsers} → ${data.targetUsers}`);
  console.log('===============================');
}