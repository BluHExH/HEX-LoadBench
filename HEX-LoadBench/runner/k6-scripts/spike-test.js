import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

// Custom metrics
export let errorRate = new Rate('errors');
export let spikeLatency = new Rate('spike_latency');

// Test configuration from environment variables
const TARGET_URL = __ENV.TARGET_URL || 'http://localhost:8080';
const TARGET_METHOD = __ENV.TARGET_METHOD || 'GET';
const TARGET_HEADERS = __ENV.TARGET_HEADERS || '{}';
const TARGET_BODY = __ENV.TARGET_BODY || '';
const AUTH_TOKEN = __ENV.AUTH_TOKEN || '';
const BASELINE_USERS = parseInt(__ENV.BASELINE_USERS) || 10;
const SPIKE_USERS = parseInt(__ENV.SPIKE_USERS) || 1000;
const SPIKE_DURATION = parseInt(__ENV.SPIKE_DURATION) || 60;
const BASELINE_DURATION = parseInt(__ENV.BASELINE_DURATION) || 300;
const MAX_RPS = parseInt(__ENV.MAX_RPS) || 5000;

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

// Configure test stages for spike testing
export let options = {
  stages: [
    { duration: '30s', target: BASELINE_USERS },           // baseline warm-up
    { duration: `${BASELINE_DURATION}s`, target: BASELINE_USERS }, // steady baseline
    { duration: '10s', target: SPIKE_USERS },              // rapid spike
    { duration: `${SPIKE_DURATION}s`, target: SPIKE_USERS }, // hold spike
    { duration: '30s', target: BASELINE_USERS },           // rapid drop
    { duration: '60s', target: 0 },                        // cool down
  ],
  thresholds: {
    http_req_duration: ['p(95)<2000'], // More lenient during spike
    http_req_failed: ['rate<0.2'],     // Allow higher error rate during spike
    errors: ['rate<0.2'],
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

  // Check response with spike-specific thresholds
  let success = check(response, {
    'status is 200': (r) => r.status === 200,
    'response time < 2000ms': (r) => r.timings.duration < 2000,
    'response time < 5000ms': (r) => r.timings.duration < 5000, // Emergency threshold
  });

  // Track errors and spike latency
  errorRate.add(!success);
  spikeLatency.add(response.timings.duration);

  // Log critical errors during spike
  if (!success && __ENV.VU % 50 === 0) {
    console.error(`SPIKE ERROR - VU ${__ENV.VU}: ${response.status} - ${response.timings.duration.toFixed(2)}ms`);
  }

  // Minimal delay for spike intensity
  sleep(0.01);
}

export function setup() {
  console.log(`=== SPIKE LOAD TEST ===`);
  console.log(`Target: ${TARGET_URL}`);
  console.log(`Method: ${TARGET_METHOD}`);
  console.log(`Baseline: ${BASELINE_USERS} users`);
  console.log(`Spike: ${SPIKE_USERS} users`);
  console.log(`Spike duration: ${SPIKE_DURATION}s`);
  console.log(`Baseline duration: ${BASELINE_DURATION}s`);
  console.log(`Max RPS: ${MAX_RPS}`);
  console.log(`====================`);
  
  return {
    startTime: new Date().toISOString(),
    baselineUsers: BASELINE_USERS,
    spikeUsers: SPIKE_USERS,
  };
}

export function teardown(data) {
  console.log('=== SPIKE TEST COMPLETED ===');
  console.log(`Start time: ${data.startTime}`);
  console.log(`End time: ${new Date().toISOString()}`);
  console.log(`Baseline users: ${data.baselineUsers}`);
  console.log(`Spike users: ${data.spikeUsers}`);
  console.log('============================');
}

// Handle test interruption for spike recovery
export function handleInterrupt(data) {
  console.log('=== SPIKE TEST INTERRUPTED ===');
  console.log('Recovery procedures activated...');
}