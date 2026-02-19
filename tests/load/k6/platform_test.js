/**
 * k6 Load Test for Admin API & Platform Services
 *
 * Tests the Admin API (FastAPI on port 8086) under sustained load.
 * Authenticates via JWT, then exercises authenticated CRUD endpoints.
 *
 * Endpoints tested:
 *   POST /auth/login          - JWT token acquisition
 *   GET  /api/v1/models       - List models
 *   GET  /api/v1/budgets      - List budgets
 *   GET  /api/v1/teams        - List teams
 *   GET  /api/v1/metrics/realtime - Realtime metrics
 *   GET  /api/v1/settings     - Platform settings
 *   GET  /health              - Health check
 *
 * Run with:
 *   k6 run tests/load/k6/platform_test.js
 *
 * Or with environment overrides:
 *   k6 run -e ADMIN_API_URL=http://admin:8086 -e API_KEY=sk-my-key tests/load/k6/platform_test.js
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend } from 'k6/metrics';
import { randomItem, randomIntBetween } from 'https://jslib.k6.io/k6-utils/1.2.0/index.js';

// ---------------------------------------------------------------------------
// Custom metrics — per-endpoint tracking
// ---------------------------------------------------------------------------
const errorRate = new Rate('error_rate');

const loginDuration     = new Trend('endpoint_login_duration');
const modelsDuration    = new Trend('endpoint_models_duration');
const budgetsDuration   = new Trend('endpoint_budgets_duration');
const teamsDuration     = new Trend('endpoint_teams_duration');
const metricsDuration   = new Trend('endpoint_metrics_duration');
const settingsDuration  = new Trend('endpoint_settings_duration');
const healthDuration    = new Trend('endpoint_health_duration');

const loginErrors     = new Rate('endpoint_login_errors');
const modelsErrors    = new Rate('endpoint_models_errors');
const budgetsErrors   = new Rate('endpoint_budgets_errors');
const teamsErrors     = new Rate('endpoint_teams_errors');
const metricsErrors   = new Rate('endpoint_metrics_errors');
const settingsErrors  = new Rate('endpoint_settings_errors');
const healthErrors    = new Rate('endpoint_health_errors');

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------
const ADMIN_API_URL = __ENV.ADMIN_API_URL || 'http://localhost:8086';
const API_KEY       = __ENV.API_KEY       || '';

// ---------------------------------------------------------------------------
// k6 options
// ---------------------------------------------------------------------------
export const options = {
  stages: [
    { duration: '30s', target: 20 },   // Warm up
    { duration: '2m',  target: 50 },   // Ramp to steady state
    { duration: '3m',  target: 50 },   // Sustained load
    { duration: '1m',  target: 0 },    // Cool down
  ],

  thresholds: {
    // Global
    'error_rate':                  ['rate<0.01'],
    'http_req_duration':           ['p(95)<500'],

    // Per-endpoint latency
    'endpoint_health_duration':    ['p(99)<100'],
    'endpoint_login_duration':     ['p(95)<500'],
    'endpoint_models_duration':    ['p(95)<500'],
    'endpoint_budgets_duration':   ['p(95)<500'],
    'endpoint_teams_duration':     ['p(95)<500'],
    'endpoint_metrics_duration':   ['p(95)<500'],
    'endpoint_settings_duration':  ['p(95)<500'],

    // Per-endpoint errors
    'endpoint_health_errors':      ['rate<0.01'],
    'endpoint_login_errors':       ['rate<0.01'],
    'endpoint_models_errors':      ['rate<0.01'],
    'endpoint_budgets_errors':     ['rate<0.01'],
    'endpoint_teams_errors':       ['rate<0.01'],
    'endpoint_metrics_errors':     ['rate<0.01'],
    'endpoint_settings_errors':    ['rate<0.01'],
  },
};

// ---------------------------------------------------------------------------
// Weighted endpoint table — health checks are frequent, login is rare
// ---------------------------------------------------------------------------
const endpoints = [
  { name: 'health',   path: '/health',                 weight: 3,  auth: false, durationMetric: healthDuration,   errorMetric: healthErrors },
  { name: 'models',   path: '/api/v1/models',          weight: 5,  auth: true,  durationMetric: modelsDuration,   errorMetric: modelsErrors },
  { name: 'budgets',  path: '/api/v1/budgets',         weight: 3,  auth: true,  durationMetric: budgetsDuration,  errorMetric: budgetsErrors },
  { name: 'teams',    path: '/api/v1/teams',           weight: 3,  auth: true,  durationMetric: teamsDuration,    errorMetric: teamsErrors },
  { name: 'metrics',  path: '/api/v1/metrics/realtime',weight: 4,  auth: true,  durationMetric: metricsDuration,  errorMetric: metricsErrors },
  { name: 'settings', path: '/api/v1/settings',        weight: 2,  auth: true,  durationMetric: settingsDuration, errorMetric: settingsErrors },
];

// Build weighted list for random selection
const weightedEndpoints = [];
for (const ep of endpoints) {
  for (let i = 0; i < ep.weight; i++) {
    weightedEndpoints.push(ep);
  }
}

// ---------------------------------------------------------------------------
// Setup — authenticate once, share JWT across VUs
// ---------------------------------------------------------------------------
export function setup() {
  // Health check first
  const healthRes = http.get(`${ADMIN_API_URL}/health`);
  if (healthRes.status !== 200) {
    console.error(`Admin API health check failed: status=${healthRes.status}`);
    throw new Error('Admin API is not healthy');
  }
  console.log('Admin API is healthy');

  // Authenticate to get JWT
  const loginPayload = JSON.stringify({ api_key: API_KEY });
  const loginRes = http.post(`${ADMIN_API_URL}/auth/login`, loginPayload, {
    headers: { 'Content-Type': 'application/json' },
    timeout: '10s',
  });

  const loginOk = check(loginRes, {
    'login status is 200': (r) => r.status === 200,
    'login returns access_token': (r) => {
      try {
        return JSON.parse(r.body).access_token !== undefined;
      } catch (e) {
        return false;
      }
    },
  });

  if (!loginOk) {
    console.error(`Login failed: status=${loginRes.status} body=${loginRes.body}`);
    throw new Error('Could not authenticate with Admin API');
  }

  const token = JSON.parse(loginRes.body).access_token;
  console.log('Authenticated successfully, starting load test');

  return { token: token, startTime: Date.now() };
}

// ---------------------------------------------------------------------------
// Main VU loop — randomly pick an endpoint and call it
// ---------------------------------------------------------------------------
export default function (data) {
  const ep = randomItem(weightedEndpoints);

  const headers = { 'Content-Type': 'application/json' };
  if (ep.auth) {
    headers['Authorization'] = `Bearer ${data.token}`;
  }

  group(ep.name, function () {
    const startTime = Date.now();

    const response = http.get(`${ADMIN_API_URL}${ep.path}`, {
      headers: headers,
      timeout: '10s',
      tags: { endpoint: ep.name },
    });

    const duration = Date.now() - startTime;
    ep.durationMetric.add(duration);

    const success = check(response, {
      [`${ep.name} status is 200`]: (r) => r.status === 200,
    });

    ep.errorMetric.add(!success);
    errorRate.add(!success);

    if (!success) {
      console.log(`[${ep.name}] Failed: status=${response.status} duration=${duration}ms`);
    }
  });

  // Also periodically re-login to test the auth endpoint under load
  if (Math.random() < 0.02) {
    group('login', function () {
      const startTime = Date.now();

      const loginPayload = JSON.stringify({ api_key: API_KEY });
      const response = http.post(`${ADMIN_API_URL}/auth/login`, loginPayload, {
        headers: { 'Content-Type': 'application/json' },
        timeout: '10s',
        tags: { endpoint: 'login' },
      });

      const duration = Date.now() - startTime;
      loginDuration.add(duration);

      const success = check(response, {
        'login status is 200': (r) => r.status === 200,
      });

      loginErrors.add(!success);
      errorRate.add(!success);
    });
  }

  sleep(randomIntBetween(1, 3) / 10);
}

// ---------------------------------------------------------------------------
// Teardown
// ---------------------------------------------------------------------------
export function teardown(data) {
  const duration = (Date.now() - data.startTime) / 1000;
  console.log(`Platform load test completed in ${duration.toFixed(1)}s`);
}
