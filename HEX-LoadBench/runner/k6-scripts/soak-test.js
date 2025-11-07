import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

// Custom metrics for soak testing
export let errorRate = new Rate('errors');
export let memoryLeakDetector = new Rate('memory_usage');
export let throughput = new Rate('throughput');

// Test configuration from environment variables
const TARGET_URL = __ENV.TARGET_URL || 'http://localhost:8080';
const TARGET_METHOD = __ENV.TARGET_METHOD || 'GET';
const TARGET_HEADERS = __ENV.TARGET_HEADERS || '{}';
const TARGET_BODY = __ENV.TARGET_BODY || '';
const AUTH_TOKEN = __ENV.AUTH_TOKEN || '';
const CONCURRENT_USERS = parseInt(__ENV.CONCURRENT_USERS) || 50;
const SOAK_DURATION = parseInt(__ENV.SOAK_DURATION) || 86400; // 24 hours default
const MAX_RPS = parseInt(__ENV.MAX_RPS) || 100;

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

// Configure test stages for soak testing (extended duration)
export let options = {
  stages: [
    { duration: '10m', target: CONCURRENT_USERS },   // gradual ramp-up
    { duration: `${SOAK_DURATION - 20}m`, target: CONCURRENT_USERS }, // extended soak
    { duration: '10m', target: 0 },                  // gradual ramp-down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],    // Strict thresholds for long duration
    http_req_failed: ['rate<0.01'],      # Very low error rate for soak
    errors: ['rate<0.01'],
    http_req_waiting: ['p(95)<100'],     # Waiting time threshold
  },
  rps: MAX_RPS,
  noConnectionReuse: true,               // Prevent connection pooling issues
  discardResponseBodies: true,           # Save memory during long tests
  insecureSkipTLSVerify: true,           # Handle cert issues during long runs
};

// Track metrics over time
let requestCount = 0;
let errorCount = 0;
let totalResponseTime = 0;
let startTime = new Date();

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

  // Increment counters
  requestCount++;
  totalResponseTime += response.timings.duration;

  // Check response with strict soak thresholds
  let success = check(response, {
    'status is 200': (r) => r.status === 200,
    'response time < 500ms': (r) => r.timings.duration < 500,
    'response time < 1000ms': (r) => r.timings.duration < 1000,
    'no timeout errors': (r) => r.status !== 0,
  });

  // Track errors and throughput
  if (!success) {
    errorCount++;
    errorRate.add(1);
    
    // Log errors periodically during soak
    if (requestCount % 1000 === 0) {
      console.error(`SOAK ERROR - Request ${requestCount}: ${response.status} - ${response.timings.duration.toFixed(2)}ms`);
    }
  } else {
    errorRate.add(0);
  }

  // Calculate current throughput
  throughput.add(1);

  // Periodic logging for long-running tests
  let currentTime = new Date();
  let elapsedMinutes = Math.floor((currentTime - startTime) / (1000 * 60));
  
  if (requestCount % 5000 === 0 || elapsedMinutes % 30 === 0) {
    let avgResponseTime = totalResponseTime / requestCount;
    let currentErrorRate = (errorCount / requestCount) * 100;
    
    console.log(`=== SOAK TEST UPDATE ===`);
    console.log(`Elapsed: ${elapsedMinutes} minutes`);
    console.log(`Requests: ${requestCount}`);
    console.log(`Errors: ${errorCount} (${currentErrorRate.toFixed(2)}%)`);
    console.log(`Avg Response: ${avgResponseTime.toFixed(2)}ms`);
    console.log(`Current VU: ${__ENV.VU}`);
    console.log(`========================`);
  }

  // Normal delay for sustained load
  sleep(1);
}

export function setup() {
  console.log(`=== SOAK LOAD TEST ===`);
  console.log(`Target: ${TARGET_URL}`);
  console.log(`Method: ${TARGET_METHOD}`);
  console.log(`Concurrent users: ${CONCURRENT_USERS}`);
  console.log(`Duration: ${SOAK_DURATION} seconds (${Math.floor(SOAK_DURATION/3600)} hours)`);
  console.log(`Max RPS: ${MAX_RPS}`);
  console.log(`Start time: ${new Date().toISOString()}`);
  console.log(`==================`);
  
  // Reset counters
  requestCount = 0;
  errorCount = 0;
  totalResponseTime = 0;
  startTime = new Date();
  
  return {
    startTime: startTime.toISOString(),
    concurrentUsers: CONCURRENT_USERS,
    duration: SOAK_DURATION,
  };
}

export function teardown(data) {
  let endTime = new Date();
  let totalDuration = Math.floor((endTime - new Date(data.startTime)) / 1000);
  let finalAvgResponseTime = totalResponseTime / requestCount;
  let finalErrorRate = (errorCount / requestCount) * 100;
  
  console.log(`=== SOAK TEST COMPLETED ===`);
  console.log(`Start time: ${data.startTime}`);
  console.log(`End time: ${endTime.toISOString()}`);
  console.log(`Total duration: ${totalDuration} seconds`);
  console.log(`Total requests: ${requestCount}`);
  console.log(`Total errors: ${errorCount} (${finalErrorRate.toFixed(2)}%)`);
  console.log(`Final avg response: ${finalAvgResponseTime.toFixed(2)}ms`);
  console.log(`Throughput: ${(requestCount/totalDuration).toFixed(2)} req/sec`);
  console.log(`============================`);
}

// Handle graceful shutdown for long tests
export function handleInterrupt(data) {
  console.log(`=== SOAK TEST INTERRUPTED ===`);
  console.log(`Partial results at interruption:`);
  console.log(`Requests processed: ${requestCount}`);
  console.log(`Errors encountered: ${errorCount}`);
  console.log(`Running time: ${Math.floor((new Date() - startTime) / 1000)} seconds`);
  console.log(`===============================`);
}