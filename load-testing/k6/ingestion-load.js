import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '20s', target: 5 },
    { duration: '30s', target: 15 },
    { duration: '60s', target: 30 },
    { duration: '30s', target: 30 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    checks: ['rate>0.95'],
  },
};

const endpoint =
  'http://telemetryscope-ingestion:8001/api/v1/logs';

export default function () {
  const payload = JSON.stringify({
    service: 'k6-hpa-test',
    environment: 'development',
    severity: 'INFO',
    message: 'TelemetryScope Kubernetes autoscaling load test',
    endpoint: '/load-test',
    status_code: 200,
    duration_ms: 25,
    request_id: `k6-${__VU}-${__ITER}`,
    metadata: {
      source: 'k6',
      test: 'ingestion-hpa',
    },
  });

  const response = http.post(endpoint, payload, {
    headers: {
      'Content-Type': 'application/json',
    },
    timeout: '10s',
  });

  check(response, {
    'event accepted with HTTP 202': (r) => r.status === 202,
  });

  sleep(0.1);
}
