import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, NavLink } from 'react-router-dom';
import { Activity, List, AlertOctagon, Server, Bell, PlaySquare, Settings } from 'lucide-react';
import Overview from './pages/Overview';
import LiveLogs from './pages/LiveLogs';
import Errors from './pages/Errors';
import Services from './pages/Services';
import Alerts from './pages/Alerts';
import LoadTest from './pages/LoadTest';
import Infrastructure from './pages/Infrastructure';

const SidebarItem = ({ to, icon: Icon, label }) => (
  <NavLink
    to={to}
    className={({ isActive }) =>
      `flex items-center px-4 py-3 text-sm font-medium transition-colors ${
        isActive
          ? 'bg-primary/10 text-primary border-r-2 border-primary'
          : 'text-text-muted hover:bg-surface hover:text-text'
      }`
    }
  >
    <Icon className="w-5 h-5 mr-3" />
    {label}
  </NavLink>
);

const Layout = ({ children }) => {
  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <div className="w-64 bg-surface-light border-r border-border flex flex-col">
        <div className="h-16 flex items-center px-6 border-b border-border">
          <div className="flex items-center text-primary font-bold text-lg">
            <Activity className="w-6 h-6 mr-2" />
            TelemetryScope
          </div>
        </div>
        
        <div className="flex-1 py-4 overflow-y-auto">
          <nav className="space-y-1">
            <SidebarItem to="/overview" icon={Activity} label="Overview" />
            <SidebarItem to="/logs" icon={List} label="Live Logs" />
            <SidebarItem to="/errors" icon={AlertOctagon} label="Errors / Issues" />
            <SidebarItem to="/services" icon={Server} label="Services" />
            <SidebarItem to="/alerts" icon={Bell} label="Alerts" />
            <SidebarItem to="/load-test" icon={PlaySquare} label="Load Test" />
            <SidebarItem to="/infrastructure" icon={Settings} label="Infrastructure" />
          </nav>
        </div>
        
        <div className="p-4 border-t border-border text-xs text-text-muted">
          v1.0.0 (demo)
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
};

function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Navigate to="/overview" replace />} />
          <Route path="/overview" element={<Overview />} />
          <Route path="/logs" element={<LiveLogs />} />
          <Route path="/errors" element={<Errors />} />
          <Route path="/services" element={<Services />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/load-test" element={<LoadTest />} />
          <Route path="/infrastructure" element={<Infrastructure />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}

export default App;
