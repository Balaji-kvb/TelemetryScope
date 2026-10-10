import React, { useState, useEffect } from 'react';
import { fetchServices } from '../services/api';
import { Server, Activity, ArrowRight } from 'lucide-react';

const Services = () => {
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await fetchServices();
        setServices(data);
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
      <h1 className="text-2xl font-bold text-text mb-6">Service Catalog</h1>
      
      {loading ? (
        <div className="p-8 flex justify-center"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div></div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {services.map(svc => (
            <div key={svc.name} className="card p-6 flex flex-col hover:border-primary/50 transition-colors cursor-pointer">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center">
                  <Server className="w-5 h-5 text-primary mr-3" />
                  <h3 className="font-semibold text-text">{svc.name}</h3>
                </div>
                <div className={`w-3 h-3 rounded-full ${svc.status === 'healthy' ? 'bg-success' : 'bg-error'}`} />
              </div>
              
              <div className="flex-1 space-y-4">
                <div>
                  <div className="text-sm text-text-muted mb-1">Replicas</div>
                  <div className="font-medium">{svc.replicas_ready} / {svc.replicas_desired}</div>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-sm text-text-muted mb-1">Error Rate</div>
                    <div className="font-medium">{(svc.error_rate * 100).toFixed(1)}%</div>
                  </div>
                  <div>
                    <div className="text-sm text-text-muted mb-1">P95 Latency</div>
                    <div className="font-medium">{svc.p95_latency_ms}ms</div>
                  </div>
                </div>
              </div>
              
              <div className="mt-6 pt-4 border-t border-border flex items-center text-sm text-primary group">
                View Logs & Metrics <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
              </div>
            </div>
          ))}
          
          <div className="card p-6 border-dashed border-2 bg-transparent flex flex-col items-center justify-center text-text-muted hover:text-text hover:border-border cursor-pointer transition-colors">
            <Activity className="w-8 h-8 mb-3 opacity-50" />
            <p className="font-medium">Connect New Service</p>
            <p className="text-sm mt-1 text-center">Setup SDK or DaemonSet</p>
          </div>
        </div>
      )}
    </div>
  );
};

export default Services;
