/**
 * k6 Load Test for AI Gateway Platform
 *
 * Tests:
 * - Sustained load at 1000+ RPS
 * - P95 latency < 2s
 * - Error rate < 1%
 *
 * Run with:
 *   k6 run load_test.js
 *
 * Or with specific VUs and duration:
 *   k6 run --vus 100 --duration 5m load_test.js
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';
import { randomItem, randomIntBetween } from 'https://jslib.k6.io/k6-utils/1.2.0/index.js';

// Custom metrics
const errorRate = new Rate('error_rate');
const requestDuration = new Trend('request_duration');
const tokensThroughput = new Counter('tokens_throughput');
const costTracked = new Counter('cost_tracked');

// Configuration from environment
const LITELLM_URL = __ENV.LITELLM_URL || 'http://localhost:4000';
const API_KEY = __ENV.API_KEY || 'sk-test-key';

// Test configuration
export const options = {
  // Stages for ramping up load
  stages: [
    { duration: '30s', target: 50 },   // Ramp up to 50 VUs
    { duration: '1m', target: 100 },   // Ramp up to 100 VUs
    { duration: '2m', target: 200 },   // Ramp up to 200 VUs
    { duration: '5m', target: 200 },   // Stay at 200 VUs (sustained load)
    { duration: '1m', target: 100 },   // Ramp down
    { duration: '30s', target: 0 },    // Ramp down to 0
  ],

  // Thresholds for pass/fail
  thresholds: {
    // P95 latency should be under 2 seconds
    'http_req_duration': ['p(95)<2000'],

    // Error rate should be under 1%
    'error_rate': ['rate<0.01'],

    // At least 95% of requests should succeed
    'http_req_failed': ['rate<0.05'],

    // Custom metrics thresholds
    'request_duration': ['p(95)<2000', 'avg<1000'],
  },
};

// Test data
const models = ['gpt-4o-mini', 'claude-3-haiku', 'fast'];
const prompts = [
  'What is 2+2?',
  'Say hello',
  'Count to 5',
  'What color is the sky?',
  'Name a fruit',
];

// Headers for all requests
const headers = {
  'Authorization': `Bearer ${API_KEY}`,
  'Content-Type': 'application/json',
};

// Main test function
export default function () {
  group('Chat Completions', function () {
    const model = randomItem(models);
    const prompt = randomItem(prompts);

    const payload = JSON.stringify({
      model: model,
      messages: [
        { role: 'user', content: prompt }
      ],
      max_tokens: randomIntBetween(10, 50),
    });

    const startTime = Date.now();

    const response = http.post(
      `${LITELLM_URL}/v1/chat/completions`,
      payload,
      { headers: headers, timeout: '30s' }
    );

    const duration = Date.now() - startTime;
    requestDuration.add(duration);

    // Check response
    const success = check(response, {
      'status is 200': (r) => r.status === 200,
      'response has choices': (r) => {
        try {
          const body = JSON.parse(r.body);
          return body.choices && body.choices.length > 0;
        } catch (e) {
          return false;
        }
      },
      'response has usage': (r) => {
        try {
          const body = JSON.parse(r.body);
          return body.usage && body.usage.total_tokens > 0;
        } catch (e) {
          return false;
        }
      },
    });

    // Track error rate
    errorRate.add(!success);

    // Track tokens if successful
    if (success && response.status === 200) {
      try {
        const body = JSON.parse(response.body);
        if (body.usage) {
          tokensThroughput.add(body.usage.total_tokens);
        }
      } catch (e) {
        // Ignore parse errors
      }
    }

    // Small sleep to avoid overwhelming the system
    sleep(randomIntBetween(1, 3) / 10);
  });
}

// Setup function - runs once before the test
export function setup() {
  // Verify connectivity
  const healthCheck = http.get(`${LITELLM_URL}/health`);

  if (healthCheck.status !== 200) {
    console.error(`Health check failed: ${healthCheck.status}`);
    throw new Error('Service not healthy');
  }

  console.log('Service is healthy, starting load test');

  return {
    startTime: Date.now(),
  };
}

// Teardown function - runs once after the test
export function teardown(data) {
  const duration = (Date.now() - data.startTime) / 1000;
  console.log(`Test completed in ${duration}s`);
}

// Scenario: Streaming requests
export function streamingScenario() {
  group('Streaming Completions', function () {
    const model = randomItem(models);

    const payload = JSON.stringify({
      model: model,
      messages: [
        { role: 'user', content: 'Count from 1 to 10 slowly.' }
      ],
      max_tokens: 100,
      stream: true,
    });

    const response = http.post(
      `${LITELLM_URL}/v1/chat/completions`,
      payload,
      { headers: headers, timeout: '60s' }
    );

    check(response, {
      'streaming status is 200': (r) => r.status === 200,
    });

    errorRate.add(response.status !== 200);
  });
}

// Scenario: Health check only (for baseline)
export function healthCheckScenario() {
  const response = http.get(`${LITELLM_URL}/health`);

  check(response, {
    'health check succeeds': (r) => r.status === 200,
  });
}

// Scenario: Model listing
export function modelListScenario() {
  const response = http.get(
    `${LITELLM_URL}/v1/models`,
    { headers: headers }
  );

  check(response, {
    'model list succeeds': (r) => r.status === 200,
    'models returned': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.data && body.data.length > 0;
      } catch (e) {
        return false;
      }
    },
  });
}
