import React, { useState, useEffect } from 'react';
import { Activity, AlertTriangle, Clock, Server, BellRing } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { format } from 'date-fns';
import { fetchOverviewStats, fetchTimeline, fetchServices } from '../services/api';

const StatCard = ({ title, value, icon: Icon, trend, trendLabel, colorClass = "text-primary" }) => (
  <div className="card p-6 flex flex-col">
    <div className="flex items-center justify-between mb-4">
      <h3 className="text-text-muted font-medium text-sm">{title}</h3>
      <div className={`p-2 rounded-lg bg-surface-light ${colorClass}`}>
        <Icon className="w-5 h-5" />
      </div>
    </div>
    <div className="text-3xl font-bold text-text mb-2">
      {value !== null ? value : '-'}
    </div>
    {trend && (
      <div className="text-sm">
        <span className={trend > 0 ? "text-error" : "text-success"}>
          {trend > 0 ? '↑' : '↓'} {Math.abs(trend)}%
        </span>
        <span className="text-text-muted ml-2">{trendLabel}</span>
      </div>
    )}
  </div>
);

const Overview = () => {
  const [stats, setStats] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadData = async () => {
    try {
      setLoading(true);
      const [overviewData, timelineData, servicesData] = await Promise.all([
        fetchOverviewStats(),
        fetchTimeline(),
        fetchServices()
      ]);

      setStats(overviewData);
      setTimeline(timelineData.points || []);
      setServices(servicesData || []);
      setError(null);
    } catch (err) {
      setError("Failed to load overview data. Is the Query Service running?");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000); // Refresh every 10s
    return () => clearInterval(interval);
  }, []);

  if (loading && !stats) {
    return <div className="p-8 flex justify-center items-center h-full"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div></div>;
  }

  if (error && !stats) {
    return <div className="p-8 text-error">{error}</div>;
  }
  const healthyServices = services.filter(
    service => service.status === 'healthy'
  ).length;

  const chartData = timeline.map(pt => ({
    time: format(new Date(pt.timestamp), 'HH:mm'),
    requests: pt.total,
    errors: pt.errors,
    latency: pt.p95_duration_ms
  }));

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-text">Overview</h1>
        <div className="text-sm text-text-muted flex items-center">
          <span className="w-2 h-2 rounded-full bg-success mr-2 animate-pulse"></span>
          Auto-refreshing
        </div>
      </div>

      {error && <div className="p-4 bg-red-900/20 text-red-400 border border-red-900/50 rounded-lg">{error}</div>}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard
          title="Events / Min"
          value={stats?.events_per_minute || 0}
          icon={Activity}
          colorClass="text-blue-400"
        />
        <StatCard
          title="Error Rate"
          value={`${((stats?.error_rate || 0) * 100).toFixed(2)}%`}
          icon={AlertTriangle}
          colorClass="text-red-400"
        />
        <StatCard
          title="P95 Latency"
          value={`${stats?.p95_latency_ms || 0}ms`}
          icon={Clock}
          colorClass="text-amber-400"
        />
        <StatCard
          title="Active Alerts"
          value={stats?.active_alerts || 0}
          icon={BellRing}
          colorClass="text-red-500"
        />
        <StatCard
          title="Healthy Services"
          value={services.length ? `${healthyServices} / ${services.length}` : '-'}
          icon={Server}
          colorClass="text-green-400"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="card p-6 lg:col-span-2">
          <h3 className="text-lg font-semibold mb-4">Traffic Timeline</h3>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorRequests" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" vertical={false} />
                <XAxis dataKey="time" stroke="#9ca3af" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#9ca3af" fontSize={12} tickLine={false} axisLine={false} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#171717', borderColor: '#374151', color: '#f3f4f6' }}
                  itemStyle={{ color: '#f3f4f6' }}
                />
                <Area type="monotone" dataKey="requests" stroke="#3b82f6" strokeWidth={2} fillOpacity={1} fill="url(#colorRequests)" name="Requests" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card p-6">
          <h3 className="text-lg font-semibold mb-4">Severity Distribution</h3>
          <div className="space-y-4 mt-8">
            {stats?.severity_distribution && Object.entries(stats.severity_distribution).sort((a, b) => b[1] - a[1]).map(([severity, count]) => {
              const colors = {
                INFO: 'bg-blue-500',
                ERROR: 'bg-red-500',
                WARNING: 'bg-amber-500',
                DEBUG: 'bg-gray-500',
                CRITICAL: 'bg-red-700'
              };
              const total = stats.total_events || 1;
              const percent = Math.round((count / total) * 100);

              return (
                <div key={severity}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-text-muted">{severity}</span>
                    <span className="font-medium">{count} ({percent}%)</span>
                  </div>
                  <div className="w-full bg-surface-light rounded-full h-2">
                    <div className={`${colors[severity] || 'bg-primary'} h-2 rounded-full`} style={{ width: `${percent}%` }}></div>
                  </div>
                </div>
              );
            })}

            {(!stats?.severity_distribution || Object.keys(stats.severity_distribution).length === 0) && (
              <div className="text-center text-text-muted py-8">No data available</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Overview;
