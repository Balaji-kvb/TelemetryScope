import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || '/api/v1';

export const api = axios.create({
  baseURL: API_URL,
  timeout: 60000,
});

export const fetchOverviewStats = async (filters = {}) => {
  const { data } = await api.get('/stats/overview', { params: filters });
  return data.data;
};

export const fetchTimeline = async (filters = {}) => {
  const { data } = await api.get('/stats/timeline', { params: filters });
  return data.data;
};

export const fetchLogs = async (params = {}) => {
  const { data } = await api.get('/logs', { params });
  return data;
};

export const fetchErrors = async (params = {}) => {
  const { data } = await api.get('/errors', { params });
  return data;
};

export const fetchErrorDetails = async (fingerprint) => {
  const { data } = await api.get(`/errors/${fingerprint}`);
  return data.data;
};

export const fetchServices = async () => {
  const { data } = await api.get('/services');
  return data.data;
};

export const fetchAlerts = async (params = {}) => {
  const { data } = await api.get('/alerts', { params });
  return data;
};

export const triggerDemoError = async (payload) => {
  const { data } = await api.post('/demo/error', payload);
  return data;
};

export const triggerDemoSlow = async (payload) => {
  const { data } = await api.post('/demo/slow', payload);
  return data;
};

export const triggerDemoTraffic = async (payload) => {
  const { data } = await api.post('/demo/traffic', payload);
  return data;
};

export const resetDemo = async () => {
  const { data } = await api.post('/demo/reset');
  return data;
};

export const getSystemStatus = async () => {
  const { data } = await api.get('/system/status');
  return data.data;
};

export const getDeployments = async () => {
  const { data } = await api.get('/deployments');
  return data.data;
};
