import React, { useState, useEffect } from 'react';
import { Settings, GitCommit, Box, Cpu } from 'lucide-react';
import { getDeployments, getSystemStatus } from '../services/api';
import { formatDistanceToNow } from 'date-fns';

const Infrastructure = () => {
  const [deployments, setDeployments] = useState([]);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [deps, sys] = await Promise.all([
          getDeployments(),
          getSystemStatus()
        ]);
        setDeployments(deps);
        setStatus(sys);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center mb-6">
        <Settings className="w-6 h-6 text-text-muted mr-3" />
        <h1 className="text-2xl font-bold text-text">Infrastructure & Deployment</h1>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="card p-6 col-span-1 md:col-span-1">
          <h3 className="font-semibold text-lg mb-4 flex items-center">
            <Cpu className="w-5 h-5 mr-2 text-primary" />
            System Status
          </h3>
          {loading ? (
            <div className="animate-pulse space-y-4">
              <div className="h-4 bg-surface-light rounded w-3/4"></div>
              <div className="h-4 bg-surface-light rounded w-1/2"></div>
            </div>
          ) : status ? (
            <dl className="space-y-4 text-sm">
              <div>
                <dt className="text-text-muted mb-1">Environment</dt>
                <dd className="font-medium">
                  <span className="badge badge-info">{status.environment}</span>
                </dd>
              </div>
              <div>
                <dt className="text-text-muted mb-1">Current Version</dt>
                <dd className="font-mono text-text">{status.version}</dd>
              </div>
              <div>
                <dt className="text-text-muted mb-1">Commit SHA</dt>
                <dd className="font-mono text-text truncate">{status.commit_sha}</dd>
              </div>
              <div>
                <dt className="text-text-muted mb-1">Database</dt>
                <dd className="flex items-center">
                  <span className={`w-2 h-2 rounded-full mr-2 ${status.database.status === 'connected' ? 'bg-success' : 'bg-error'}`}></span>
                  {status.database.status}
                </dd>
              </div>
              <div>
                <dt className="text-text-muted mb-1">Uptime</dt>
                <dd>{Math.floor(status.uptime_seconds / 3600)}h {Math.floor((status.uptime_seconds % 3600) / 60)}m</dd>
              </div>
            </dl>
          ) : (
            <div className="text-text-muted text-sm">Failed to load status.</div>
          )}
        </div>

        <div className="card p-6 col-span-1 md:col-span-2">
          <h3 className="font-semibold text-lg mb-4 flex items-center">
            <Box className="w-5 h-5 mr-2 text-primary" />
            Deployment History
          </h3>
          
          {loading ? (
            <div className="flex justify-center p-8"><div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div></div>
          ) : deployments.length === 0 ? (
            <div className="text-center p-8 border border-dashed border-border rounded-lg text-text-muted">
              <GitCommit className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>No deployments recorded.</p>
              <p className="text-xs mt-1">Deployments via CI/CD will appear here.</p>
            </div>
          ) : (
            <div className="relative border-l border-border ml-3 space-y-6">
              {deployments.map((dep, idx) => (
                <div key={dep.id || idx} className="relative pl-6">
                  <div className={`absolute -left-1.5 w-3 h-3 rounded-full border-2 border-surface ${dep.status === 'success' ? 'bg-success' : dep.status === 'failed' ? 'bg-error' : 'bg-primary animate-pulse'}`}></div>
                  <div className="flex items-center justify-between mb-1">
                    <div className="font-medium text-text">{dep.version}</div>
                    <div className="text-xs text-text-muted">
                      {formatDistanceToNow(new Date(dep.deployed_at), { addSuffix: true })}
                    </div>
                  </div>
                  <div className="text-sm text-text-muted mb-2">
                    Deployed to <span className="font-mono text-xs">{dep.environment}</span> by {dep.deployed_by}
                  </div>
                  <div className="flex items-center space-x-3 text-xs">
                    <span className="flex items-center font-mono">
                      <GitCommit className="w-3 h-3 mr-1" />
                      {dep.commit_sha.substring(0, 7)}
                    </span>
                    <a href={`https://github.com/example/repo/commit/${dep.commit_sha}`} className="text-primary hover:underline">
                      View diff
                    </a>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Infrastructure;
