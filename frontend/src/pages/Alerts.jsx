import React, { useState, useEffect } from 'react';
import { fetchAlerts } from '../services/api';
import { Bell, CheckCircle } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

const Alerts = () => {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await fetchAlerts();
        setAlerts(data.data || []);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    load();
    const interval = setInterval(load, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-text mb-1">Active Alerts</h1>
          <p className="text-text-muted text-sm">Rules evaluated by Processing Service</p>
        </div>
      </div>

      {loading && alerts.length === 0 ? (
        <div className="p-8 flex justify-center"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div></div>
      ) : alerts.length === 0 ? (
        <div className="card p-12 text-center text-text-muted flex flex-col items-center">
          <div className="w-16 h-16 bg-success/10 rounded-full flex items-center justify-center mb-4">
            <CheckCircle className="w-8 h-8 text-success" />
          </div>
          <h3 className="text-lg font-medium text-text mb-2">System Healthy</h3>
          <p>No active alerts. Everything is running smoothly.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {alerts.map(alert => (
            <div key={alert.id} className="card p-6 flex items-start">
              <div className="mr-4 mt-1">
                <Bell className={`w-6 h-6 ${alert.severity === 'CRITICAL' ? 'text-error' : 'text-warning'}`} />
              </div>
              <div className="flex-1">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center space-x-3">
                    <span className="font-bold text-text">{alert.rule}</span>
                    <span className={`badge ${alert.severity === 'CRITICAL' ? 'badge-critical' : 'badge-warning'}`}>
                      {alert.severity}
                    </span>
                    <span className="text-sm font-medium text-text-muted">on {alert.service}</span>
                  </div>
                  <span className="text-sm text-text-muted">
                    {formatDistanceToNow(new Date(alert.triggered_at), { addSuffix: true })}
                  </span>
                </div>
                <p className="text-text mb-4">{alert.message}</p>
                
                <div className="flex space-x-3">
                  <button className="btn btn-secondary py-1 px-3 text-xs">Acknowledge</button>
                  <button className="btn btn-secondary py-1 px-3 text-xs">View Logs</button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default Alerts;
