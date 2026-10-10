import React, { useState, useEffect, useRef } from 'react';
import { Search, Filter, Play, Pause, ChevronDown, ChevronRight, Terminal, RefreshCw } from 'lucide-react';
import { format } from 'date-fns';
import { fetchLogs } from '../services/api';

const SeverityBadge = ({ severity }) => {
  const colors = {
    INFO: 'badge-info',
    ERROR: 'badge-error',
    WARNING: 'badge-warning',
    DEBUG: 'badge-secondary',
    CRITICAL: 'badge-critical'
  };
  return (
    <span className={`badge ${colors[severity] || 'badge-secondary'}`}>
      {severity}
    </span>
  );
};

const LogRow = ({ log, expanded, onToggle }) => (
  <>
    <tr 
      className={`border-b border-border hover:bg-surface-light cursor-pointer transition-colors ${expanded ? 'bg-surface-light' : ''}`}
      onClick={onToggle}
    >
      <td className="px-4 py-3 whitespace-nowrap text-sm text-text-muted w-10">
        {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
      </td>
      <td className="px-4 py-3 whitespace-nowrap text-sm text-text-muted">
        {format(new Date(log.timestamp), 'HH:mm:ss.SSS')}
      </td>
      <td className="px-4 py-3 whitespace-nowrap text-sm">
        <SeverityBadge severity={log.severity} />
      </td>
      <td className="px-4 py-3 whitespace-nowrap text-sm font-medium">
        {log.service}
      </td>
      <td className="px-4 py-3 text-sm font-mono text-text truncate max-w-xl">
        {log.message}
      </td>
    </tr>
    {expanded && (
      <tr>
        <td colSpan="5" className="px-4 py-4 bg-background/50 border-b border-border">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">Properties</h4>
              <dl className="grid grid-cols-1 gap-x-4 gap-y-2 text-sm">
                <div className="flex">
                  <dt className="w-32 text-text-muted">ID</dt>
                  <dd className="font-mono text-xs">{log.id}</dd>
                </div>
                <div className="flex">
                  <dt className="w-32 text-text-muted">Request ID</dt>
                  <dd className="font-mono text-xs text-primary">{log.request_id || '-'}</dd>
                </div>
                <div className="flex">
                  <dt className="w-32 text-text-muted">Fingerprint</dt>
                  <dd className="font-mono text-xs">{log.fingerprint || '-'}</dd>
                </div>
                <div className="flex">
                  <dt className="w-32 text-text-muted">Environment</dt>
                  <dd>{log.environment}</dd>
                </div>
                <div className="flex">
                  <dt className="w-32 text-text-muted">Endpoint</dt>
                  <dd className="font-mono text-xs">{log.endpoint || '-'}</dd>
                </div>
                <div className="flex">
                  <dt className="w-32 text-text-muted">Status / Duration</dt>
                  <dd>{log.status_code || '-'} / {log.duration_ms ? `${log.duration_ms}ms` : '-'}</dd>
                </div>
              </dl>
            </div>
            <div>
              <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">Raw JSON</h4>
              <pre className="bg-background border border-border rounded-md p-3 text-xs font-mono text-text overflow-x-auto">
                {JSON.stringify(log, null, 2)}
              </pre>
            </div>
          </div>
        </td>
      </tr>
    )}
  </>
);

const LiveLogs = () => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isPaused, setIsPaused] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(new Date());
  const [expandedRows, setExpandedRows] = useState(new Set());
  
  const [filters, setFilters] = useState({
    search: '',
    service: '',
    severity: '',
  });

  const loadData = async () => {
    if (isPaused) return;
    try {
      const data = await fetchLogs({ ...filters, page_size: 100 });
      setLogs(data.data || []);
      setLastUpdated(new Date());
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 2000); // 2s polling per requirements
    return () => clearInterval(interval);
  }, [isPaused, filters]);

  const toggleRow = (id) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedRows(newExpanded);
  };

  const handleFilterChange = (e) => {
    const { name, value } = e.target;
    setFilters(prev => ({ ...prev, [name]: value }));
  };

  return (
    <div className="flex flex-col h-full">
      <div className="bg-surface border-b border-border p-4 shrink-0 flex items-center justify-between">
        <div className="flex items-center space-x-4 flex-1">
          <div className="relative w-96">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
            <input 
              type="text" 
              name="search"
              placeholder="Search logs..." 
              value={filters.search}
              onChange={handleFilterChange}
              className="input pl-10"
            />
          </div>
          
          <div className="flex items-center space-x-2">
            <Filter className="w-4 h-4 text-text-muted" />
            <select name="severity" value={filters.severity} onChange={handleFilterChange} className="input w-32 py-1 h-9">
              <option value="">All Levels</option>
              <option value="ERROR">Error</option>
              <option value="WARNING">Warning</option>
              <option value="INFO">Info</option>
              <option value="DEBUG">Debug</option>
            </select>
          </div>
          
          <select name="service" value={filters.service} onChange={handleFilterChange} className="input w-40 py-1 h-9">
            <option value="">All Services</option>
            <option value="demo-api">demo-api</option>
            <option value="telemetryscope-ingestion">ingestion</option>
            <option value="telemetryscope-processing">processing</option>
            <option value="telemetryscope-query">query</option>
          </select>
        </div>
        
        <div className="flex items-center space-x-4">
          <div className="text-xs text-text-muted flex items-center">
            <RefreshCw className={`w-3 h-3 mr-1 ${loading || !isPaused ? 'animate-spin' : ''}`} />
            Updated {format(lastUpdated, 'HH:mm:ss')}
          </div>
          <button 
            onClick={() => setIsPaused(!isPaused)}
            className={`btn ${isPaused ? 'btn-primary' : 'btn-secondary'} py-1.5 h-9`}
          >
            {isPaused ? <Play className="w-4 h-4 mr-2" /> : <Pause className="w-4 h-4 mr-2" />}
            {isPaused ? 'Resume' : 'Pause'}
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto bg-background">
        <table className="w-full text-left border-collapse">
          <thead className="bg-surface sticky top-0 z-10 shadow-sm">
            <tr>
              <th className="px-4 py-2 text-xs font-semibold text-text-muted w-10"></th>
              <th className="px-4 py-2 text-xs font-semibold text-text-muted w-32">Timestamp</th>
              <th className="px-4 py-2 text-xs font-semibold text-text-muted w-24">Level</th>
              <th className="px-4 py-2 text-xs font-semibold text-text-muted w-48">Service</th>
              <th className="px-4 py-2 text-xs font-semibold text-text-muted">Message</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {logs.length === 0 ? (
              <tr>
                <td colSpan="5" className="px-4 py-12 text-center text-text-muted">
                  <Terminal className="w-8 h-8 mx-auto mb-3 opacity-20" />
                  No logs found matching criteria
                </td>
              </tr>
            ) : (
              logs.map(log => (
                <LogRow 
                  key={log.id} 
                  log={log} 
                  expanded={expandedRows.has(log.id)}
                  onToggle={() => toggleRow(log.id)}
                />
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default LiveLogs;
