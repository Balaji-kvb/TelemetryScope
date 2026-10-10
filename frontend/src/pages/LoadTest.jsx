import React, { useState, useCallback } from 'react';
import { PlaySquare, AlertOctagon, Clock, Activity, StopCircle } from 'lucide-react';
import { triggerDemoError, triggerDemoSlow, triggerDemoTraffic, resetDemo } from '../services/api';

const LoadTest = () => {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState({});

  const handleAction = useCallback(async (action, payload, buttonKey) => {
    // Prevent double-clicks
    if (loading[buttonKey]) return;

    setLoading(prev => ({ ...prev, [buttonKey]: true }));
    setStatus(null);
    try {
      let result;
      if (action === 'error') {
        result = await triggerDemoError(payload);
        const data = result.data || {};
        setStatus({
          type: 'success',
          message: `✓ ${data.message || `${payload.count} ${payload.error_type} events generating in background`}`
        });
      } else if (action === 'slow') {
        result = await triggerDemoSlow(payload);
        const data = result.data || {};
        setStatus({
          type: 'success',
          message: `✓ ${data.message || `${payload.count} slow requests (${payload.delay_ms}ms) generating in background`}`
        });
      } else if (action === 'traffic') {
        result = await triggerDemoTraffic(payload);
        const data = result.data || {};
        setStatus({
          type: 'success',
          message: `✓ ${data.message || `Traffic burst started: ${payload.rate_per_second} RPS for ${payload.duration_seconds}s`}`
        });
      } else if (action === 'reset') {
        result = await resetDemo();
        setStatus({
          type: 'success',
          message: '✓ All active injections stopped'
        });
      }
    } catch (err) {
      const errorMsg = err.response?.data?.error?.message || err.message;
      setStatus({
        type: 'error',
        message: `Error: ${errorMsg}`
      });
    } finally {
      setLoading(prev => ({ ...prev, [buttonKey]: false }));
    }
  }, [loading]);

  const isAnyLoading = Object.values(loading).some(Boolean);

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-text mb-2 flex items-center">
          <PlaySquare className="w-6 h-6 mr-3 text-primary" />
          Load Test & Simulation
        </h1>
        <p className="text-text-muted">
          Inject synthetic anomalies into the demo workload. Events are generated immediately and traverse the full pipeline: Demo → Ingestion → Processing → PostgreSQL.
        </p>
      </div>

      {status && (
        <div className={`p-4 rounded-md border ${status.type === 'error' ? 'bg-red-900/20 border-red-900/50 text-red-400' : 'bg-green-900/20 border-green-900/50 text-green-400'}`}>
          {status.message}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Error Injection */}
        <div className="card p-6">
          <div className="flex items-center mb-4">
            <div className="p-2 bg-red-500/10 rounded-lg mr-3">
              <AlertOctagon className="w-6 h-6 text-error" />
            </div>
            <h3 className="text-lg font-semibold">Error Spikes</h3>
          </div>
          <p className="text-sm text-text-muted mb-6">
            Generate error events immediately through the telemetry pipeline. Tests error grouping and alert rules.
          </p>
          <div className="space-y-3">
            <button 
              disabled={loading['db-timeout']}
              onClick={() => handleAction('error', { count: 10, error_type: 'database_timeout' }, 'db-timeout')}
              className="btn btn-secondary w-full justify-between"
            >
              <span>{loading['db-timeout'] ? 'Generating...' : '10x DB Timeouts'}</span>
              <span className="text-xs text-text-muted border border-border px-2 py-0.5 rounded">ERROR</span>
            </button>
            <button 
              disabled={loading['payment']}
              onClick={() => handleAction('error', { count: 50, error_type: 'payment_failed' }, 'payment')}
              className="btn btn-secondary w-full justify-between"
            >
              <span>{loading['payment'] ? 'Generating...' : '50x Payment Failures'}</span>
              <span className="text-xs text-text-muted border border-border px-2 py-0.5 rounded">WARNING</span>
            </button>
          </div>
        </div>

        {/* Latency Injection */}
        <div className="card p-6">
          <div className="flex items-center mb-4">
            <div className="p-2 bg-amber-500/10 rounded-lg mr-3">
              <Clock className="w-6 h-6 text-warning" />
            </div>
            <h3 className="text-lg font-semibold">Latency Degradation</h3>
          </div>
          <p className="text-sm text-text-muted mb-6">
            Inject high-latency requests that traverse the full pipeline. Tests P95_LATENCY_HIGH alert rule.
          </p>
          <div className="space-y-3">
            <button 
              disabled={loading['slow-1500']}
              onClick={() => handleAction('slow', { count: 20, delay_ms: 1500 }, 'slow-1500')}
              className="btn btn-secondary w-full justify-between"
            >
              <span>{loading['slow-1500'] ? 'Generating...' : '20x Slow Requests (1.5s)'}</span>
            </button>
            <button 
              disabled={loading['slow-5000']}
              onClick={() => handleAction('slow', { count: 100, delay_ms: 5000 }, 'slow-5000')}
              className="btn btn-secondary w-full justify-between"
            >
              <span>{loading['slow-5000'] ? 'Generating...' : '100x Hung Requests (5s)'}</span>
            </button>
          </div>
        </div>

        {/* Traffic Burst */}
        <div className="card p-6">
          <div className="flex items-center mb-4">
            <div className="p-2 bg-blue-500/10 rounded-lg mr-3">
              <Activity className="w-6 h-6 text-primary" />
            </div>
            <h3 className="text-lg font-semibold">Traffic Burst</h3>
          </div>
          <p className="text-sm text-text-muted mb-6">
            Generate sustained background traffic to test HPA scaling and ingestion throughput.
          </p>
          <div className="space-y-3">
            <button 
              disabled={loading['traffic-50']}
              onClick={() => handleAction('traffic', { duration_seconds: 30, rate_per_second: 50 }, 'traffic-50')}
              className="btn btn-secondary w-full justify-between"
            >
              <span>{loading['traffic-50'] ? 'Starting...' : '50 RPS for 30s'}</span>
            </button>
            <button 
              disabled={loading['traffic-200']}
              onClick={() => handleAction('traffic', { duration_seconds: 60, rate_per_second: 200 }, 'traffic-200')}
              className="btn btn-secondary w-full justify-between"
            >
              <span>{loading['traffic-200'] ? 'Starting...' : '200 RPS for 60s (Stress Test)'}</span>
            </button>
          </div>
        </div>
        
        {/* State Management */}
        <div className="card p-6 border-dashed border-2 bg-transparent">
          <div className="flex items-center mb-4">
            <h3 className="text-lg font-semibold text-text-muted">Environment Control</h3>
          </div>
          <div className="space-y-3 mt-8">
            <button 
              disabled={loading['reset']}
              onClick={() => handleAction('reset', null, 'reset')}
              className="btn btn-secondary w-full text-text-muted hover:text-text"
            >
              <StopCircle className="w-4 h-4 mr-2" />
              {loading['reset'] ? 'Stopping...' : 'Stop All Active Injections'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoadTest;
