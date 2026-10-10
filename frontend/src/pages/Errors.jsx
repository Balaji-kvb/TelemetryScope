import React, { useState, useEffect } from 'react';
import { formatDistanceToNow } from 'date-fns';
import { fetchErrors } from '../services/api';
import { AlertCircle } from 'lucide-react';

const Errors = () => {
  const [errors, setErrors] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    try {
      const data = await fetchErrors();
      setErrors(data.data || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, []);

  if (loading && errors.length === 0) {
    return <div className="p-8 flex justify-center"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div></div>;
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-text mb-1">Errors & Issues</h1>
          <p className="text-text-muted text-sm">Grouped by deterministic fingerprinting</p>
        </div>
      </div>

      <div className="space-y-4">
        {errors.length === 0 ? (
          <div className="card p-12 text-center text-text-muted">
            <AlertCircle className="w-12 h-12 mx-auto mb-4 opacity-20" />
            <p>No error groups found.</p>
          </div>
        ) : (
          errors.map(error => (
            <div key={error.fingerprint} className="card p-6 flex items-start group hover:border-primary/50 transition-colors">
              <div className={`mt-1 mr-4 w-2 h-2 rounded-full shrink-0 ${error.severity === 'CRITICAL' ? 'bg-red-600' : 'bg-amber-500'}`} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center space-x-3">
                    <span className="font-mono text-xs px-2 py-1 bg-surface-light rounded text-text-muted">
                      {error.fingerprint}
                    </span>
                    <span className="text-sm font-medium text-text">{error.service}</span>
                  </div>
                  <div className="flex items-center space-x-4 text-sm text-text-muted">
                    <span>
                      <strong className="text-text">{error.occurrences}</strong> events
                    </span>
                    <span>
                      Last seen {formatDistanceToNow(new Date(error.last_seen), { addSuffix: true })}
                    </span>
                  </div>
                </div>
                <div className="text-text font-mono text-sm bg-background p-3 rounded border border-border mt-3 truncate">
                  {error.example_message}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default Errors;
