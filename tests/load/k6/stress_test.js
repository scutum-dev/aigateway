/**
 * k6 Stress Test for AI Gateway Platform
 *
 * Purpose: Find the breaking point of the system
 *
 * Run with:
 *   k6 run stress_test.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';
import { randomItem, randomIntBetween } from 'https://jslib.k6.io/k6-utils/1.2.0/index.js';

// Custom metrics
const errorRate = new Rate('error_rate');
const requestDuration = new Trend('request_duration');

// Configuration
const LITELLM_URL = __ENV.LITELLM_URL || 'http://localhost:4000';
const API_KEY = __ENV.API_KEY || 'sk-test-key';

// Stress test configuration - gradually increase load until failure
export const options = {
  stages: [
    { duration: '2m', target: 100 },   // Warm up
    { duration: '5m', target: 100 },   // Stay at 100
    { duration: '2m', target: 200 },   // Increase to 200
    { duration: '5m', target: 200 },   // Stay at 200
    { duration: '2m', target: 300 },   // Increase to 300
    { duration: '5m', target: 300 },   // Stay at 300
    { duration: '2m', target: 400 },   // Increase to 400
    { duration: '5m', target: 400 },   // Stay at 400
    { duration: '2m', target: 500 },   // Increase to 500 (stress)
    { duration: '5m', target: 500 },   // Stay at 500
    { duration: '10m', target: 0 },    // Recovery
  ],

  thresholds: {
    // More lenient thresholds for stress test
    'http_req_duration': ['p(99)<5000'],  // P99 under 5s
    'error_rate': ['rate<0.1'],            // Up to 10% errors acceptable
  },
};

const headers = {
  'Authorization': `Bearer ${API_KEY}`,
  'Content-Type': 'application/json',
};

const models = ['gpt-4o-mini', 'claude-3-haiku', 'fast'];
const prompts = [
  'What is 2+2?',
  'Hello',
  'Hi',
];

export default function () {
  const model = randomItem(models);
  const prompt = randomItem(prompts);

  const payload = JSON.stringify({
    model: model,
    messages: [{ role: 'user', content: prompt }],
    max_tokens: 10,
  });

  const startTime = Date.now();

  const response = http.post(
    `${LITELLM_URL}/v1/chat/completions`,
    payload,
    { headers: headers, timeout: '60s' }
  );

  const duration = Date.now() - startTime;
  requestDuration.add(duration);

  const success = check(response, {
    'status is 200': (r) => r.status === 200,
  });

  errorRate.add(!success);

  // Log failures for analysis
  if (!success) {
    console.log(`Failed request: status=${response.status}, duration=${duration}ms`);
  }

  sleep(randomIntBetween(1, 5) / 10);
}
