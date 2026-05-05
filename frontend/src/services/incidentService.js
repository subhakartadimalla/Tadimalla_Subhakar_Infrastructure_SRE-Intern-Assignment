import { api } from "./api.js";

export async function listIncidents() {
  const res = await api.get("/incidents");
  return res.data;
}

export async function getIncidentById(id) {
  const res = await api.get(`/incidents/${id}`);
  return res.data;
}

export async function transitionIncidentState(id, action) {
  const res = await api.post(`/incidents/${id}/state`, { action });
  return res.data;
}

export async function submitRCA(id, payload) {
  const res = await api.post(`/incidents/${id}/rca`, payload);
  return res.data;
}

export async function getRCA(id) {
  const res = await api.get(`/incidents/${id}/rca`);
  return res.data;
}

