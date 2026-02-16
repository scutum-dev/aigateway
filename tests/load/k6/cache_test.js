/**
 * k6 Load Test for Semantic Cache Service
 *
 * Tests the Semantic Cache service (FastAPI on port 8083) under sustained load.
 * Exercises cache lookup, store, and stats endpoints with synthetic embeddings.
 *
 * Endpoints tested:
 *   POST /lookup   - Cache lookup with messages (generates embeddings internally)
 *   POST /store    - Store a new cache entry
 *   GET  /stats    - Cache statistics
 *   GET  /health   - Health check
 *
 * Note: The real service calls an embedding model to generate vectors. This test
 * sends realistic request payloads and lets the service handle embedding generation.
 * If the embedding model is unavailable, lookup/store requests will fail with 5xx
 * but health and stats endpoints will still be tested.
 *
 * Run with:
 *   k6 run tests/load/k6/cache_test.js
 *
 * Or with environment overrides:
 *   k6 run -e CACHE_URL=http://cache:8083 tests/load/k6/cache_test.js
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';
import { randomItem, randomIntBetween } from 'https://jslib.k6.io/k6-utils/1.2.0/index.js';

// ---------------------------------------------------------------------------
// Custom metrics
// ---------------------------------------------------------------------------
const errorRate = new Rate('error_rate');

const lookupDuration  = new Trend('cache_lookup_duration');
const storeDuration   = new Trend('cache_store_duration');
const statsDuration   = new Trend('cache_stats_duration');
const healthDuration  = new Trend('cache_health_duration');

const lookupErrors  = new Rate('cache_lookup_errors');
const storeErrors   = new Rate('cache_store_errors');
const statsErrors   = new Rate('cache_stats_errors');
const healthErrors  = new Rate('cache_health_errors');

const cacheHits   = new Counter('cache_hits');
const cacheMisses = new Counter('cache_misses');

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------
const CACHE_URL    = __ENV.CACHE_URL    || 'http://localhost:8083';
const SERVICE_KEY  = __ENV.SERVICE_KEY  || '';
const LITELLM_KEY = __ENV.LITELLM_KEY  || '';

// ---------------------------------------------------------------------------
// k6 options
// ---------------------------------------------------------------------------
export const options = {
  stages: [
    { duration: '20s', target: 10 },   // Warm up
    { duration: '1m',  target: 30 },   // Ramp to steady state
    { duration: '3m',  target: 30 },   // Sustained load
    { duration: '30s', target: 0 },    // Cool down
  ],

  thresholds: {
    // Global
    'error_rate':               ['rate<0.01'],

    // Cache lookup is the hot path — must be fast
    'cache_lookup_duration':    ['p(95)<200'],
    'cache_store_duration':     ['p(95)<500'],
    'cache_stats_duration':     ['p(95)<300'],
    'cache_health_duration':    ['p(99)<100'],

    // Per-endpoint errors
    'cache_lookup_errors':      ['rate<0.01'],
    'cache_store_errors':       ['rate<0.01'],
    'cache_stats_errors':       ['rate<0.01'],
    'cache_health_errors':      ['rate<0.01'],
  },
};

// ---------------------------------------------------------------------------
// Test data — models and prompts to exercise tag-filtered vector search
// ---------------------------------------------------------------------------
const models = [
  'gpt-4o-mini',
  'gpt-4o',
  'claude-3-haiku',
  'claude-3-5-sonnet',
];

const userIds = [
  'user-load-test-1',
  'user-load-test-2',
  'user-load-test-3',
  null,
];

const teamIds = [
  'team-alpha',
  'team-beta',
  null,
];

// Prompts designed to produce overlapping semantics (test cache hits)
const prompts = [
  'What is the capital of France?',
  'What is the capital city of France?',
  'Tell me the capital of France.',
  'Name the capital of Germany.',
  'What is the capital of Germany?',
  'Explain how photosynthesis works.',
  'How does photosynthesis work?',
  'Describe the process of photosynthesis.',
  'What is machine learning?',
  'Define machine learning.',
  'What is 2 + 2?',
  'How much is two plus two?',
  'Summarize the theory of relativity.',
  'What is Einstein\'s theory of relativity?',
  'Write a haiku about programming.',
];

// Fake LLM response template for store requests
function makeFakeResponse(model, prompt) {
  return {
    id: `chatcmpl-loadtest-${Date.now()}`,
    object: 'chat.completion',
    created: Math.floor(Date.now() / 1000),
    model: model,
    choices: [
      {
        index: 0,
        message: {
          role: 'assistant',
          content: `This is a cached response for: ${prompt.substring(0, 50)}`,
        },
        finish_reason: 'stop',
      },
    ],
    usage: {
      prompt_tokens: randomIntBetween(10, 50),
      completion_tokens: randomIntBetween(20, 200),
      total_tokens: randomIntBetween(30, 250),
    },
  };
}

// ---------------------------------------------------------------------------
// Helper — build headers with optional service key and auth
// ---------------------------------------------------------------------------
function getHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  if (SERVICE_KEY) {
    headers['X-Service-Key'] = SERVICE_KEY;
  }
  if (LITELLM_KEY) {
    headers['Authorization'] = `Bearer ${LITELLM_KEY}`;
  }
  return headers;
}

// ---------------------------------------------------------------------------
// Setup — verify connectivity
// ---------------------------------------------------------------------------
export function setup() {
  const healthRes = http.get(`${CACHE_URL}/health`);
  if (healthRes.status !== 200) {
    console.error(`Semantic Cache health check failed: status=${healthRes.status}`);
    throw new Error('Semantic Cache is not healthy');
  }

  const body = JSON.parse(healthRes.body);
  console.log(`Semantic Cache is healthy — redis=${body.redis}, threshold=${body.similarity_threshold}`);

  // Seed a few cache entries so lookups can produce hits
  const headers = getHeaders();
  let seeded = 0;
  const seedPrompts = prompts.slice(0, 5);

  for (const prompt of seedPrompts) {
    const model = randomItem(models);
    const storePayload = JSON.stringify({
      messages: [{ role: 'user', content: prompt }],
      model: model,
      response: makeFakeResponse(model, prompt),
      user_id: 'user-load-test-1',
      input_tokens: randomIntBetween(10, 30),
      output_tokens: randomIntBetween(20, 100),
    });

    const res = http.post(`${CACHE_URL}/store`, storePayload, {
      headers: headers,
      timeout: '10s',
    });

    if (res.status === 200) {
      seeded++;
    }
  }

  console.log(`Seeded ${seeded}/${seedPrompts.length} cache entries for load test`);

  return { startTime: Date.now() };
}

// ---------------------------------------------------------------------------
// Main VU loop
// ---------------------------------------------------------------------------
export default function (data) {
  const headers = getHeaders();
  const model = randomItem(models);
  const userId = randomItem(userIds);
  const teamId = randomItem(teamIds);
  const prompt = randomItem(prompts);

  // Decide which operation to perform (weighted)
  const roll = Math.random();

  if (roll < 0.45) {
    // 45% — Cache lookup (the hot path)
    group('cache_lookup', function () {
      const payload = JSON.stringify({
        messages: [{ role: 'user', content: prompt }],
        model: model,
        user_id: userId,
        team_id: teamId,
      });

      const startTime = Date.now();
      const response = http.post(`${CACHE_URL}/lookup`, payload, {
        headers: headers,
        timeout: '10s',
        tags: { endpoint: 'lookup' },
      });
      const duration = Date.now() - startTime;
      lookupDuration.add(duration);

      const success = check(response, {
        'lookup status is 200': (r) => r.status === 200,
        'lookup returns hit field': (r) => {
          try {
            return JSON.parse(r.body).hit !== undefined;
          } catch (e) {
            return false;
          }
        },
      });

      lookupErrors.add(!success);
      errorRate.add(!success);

      // Track hit/miss
      if (success && response.status === 200) {
        try {
          const body = JSON.parse(response.body);
          if (body.hit) {
            cacheHits.add(1);
          } else {
            cacheMisses.add(1);
          }
        } catch (e) {
          // ignore
        }
      }
    });

  } else if (roll < 0.75) {
    // 30% — Cache store
    group('cache_store', function () {
      const fakeResponse = makeFakeResponse(model, prompt);
      const payload = JSON.stringify({
        messages: [{ role: 'user', content: prompt }],
        model: model,
        response: fakeResponse,
        user_id: userId,
        team_id: teamId,
        input_tokens: randomIntBetween(10, 50),
        output_tokens: randomIntBetween(20, 200),
      });

      const startTime = Date.now();
      const response = http.post(`${CACHE_URL}/store`, payload, {
        headers: headers,
        timeout: '10s',
        tags: { endpoint: 'store' },
      });
      const duration = Date.now() - startTime;
      storeDuration.add(duration);

      const success = check(response, {
        'store status is 200': (r) => r.status === 200,
        'store returns cache_key': (r) => {
          try {
            return JSON.parse(r.body).cache_key !== undefined;
          } catch (e) {
            return false;
          }
        },
      });

      storeErrors.add(!success);
      errorRate.add(!success);
    });

  } else if (roll < 0.90) {
    // 15% — Stats
    group('cache_stats', function () {
      const startTime = Date.now();
      const response = http.get(`${CACHE_URL}/stats`, {
        headers: headers,
        timeout: '10s',
        tags: { endpoint: 'stats' },
      });
      const duration = Date.now() - startTime;
      statsDuration.add(duration);

      const success = check(response, {
        'stats status is 200': (r) => r.status === 200,
        'stats returns total_entries': (r) => {
          try {
            return JSON.parse(r.body).total_entries !== undefined;
          } catch (e) {
            return false;
          }
        },
      });

      statsErrors.add(!success);
      errorRate.add(!success);
    });

  } else {
    // 10% — Health check
    group('cache_health', function () {
      const startTime = Date.now();
      const response = http.get(`${CACHE_URL}/health`, {
        timeout: '5s',
        tags: { endpoint: 'health' },
      });
      const duration = Date.now() - startTime;
      healthDuration.add(duration);

      const success = check(response, {
        'health status is 200': (r) => r.status === 200,
        'health redis connected': (r) => {
          try {
            return JSON.parse(r.body).redis === 'connected';
          } catch (e) {
            return false;
          }
        },
      });

      healthErrors.add(!success);
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
  console.log(`Cache load test completed in ${duration.toFixed(1)}s`);
}
