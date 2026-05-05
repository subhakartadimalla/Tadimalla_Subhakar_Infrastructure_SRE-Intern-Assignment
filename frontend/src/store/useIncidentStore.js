import { create } from "zustand";
import * as incidentService from "../services/incidentService.js";

const MAX_GRAPH_POINTS = 10;

function buildSnapshot(incidents) {
  const arr = Array.isArray(incidents) ? incidents : [];
  const p0 = arr.filter((i) => String(i.severity).toUpperCase() === "P0").length;
  const p1 = arr.filter((i) => String(i.severity).toUpperCase() === "P1").length;
  const p2 = arr.filter((i) => String(i.severity).toUpperCase() === "P2").length;
  const signals = arr.reduce((sum, i) => sum + (Number(i.signal_count) || 0), 0);
  const now = new Date();
  const time = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}:${String(now.getSeconds()).padStart(2, "0")}`;
  return { time, total: arr.length, p0, p1, p2, signals };
}

export const useIncidentStore = create((set, get) => ({
  activeIncidents: [],
  selectedIncident: null,
  loading: false,
  error: null,

  // Stats derived from current activeIncidents
  stats: {
    totalIncidents: 0,
    severityCounts: { P0: 0, P1: 0, P2: 0 },
  },

  // Time-series snapshots for the graph (max MAX_GRAPH_POINTS)
  graphData: [],

  clearError: () => set({ error: null }),

  fetchIncidents: async () => {
    if (get().loading) return get().activeIncidents;
    set({ loading: true, error: null });
    try {
      const incidents = await incidentService.listIncidents();
      const arr = Array.isArray(incidents) ? incidents : [];

      // Recompute stats
      const p0 = arr.filter((i) => String(i.severity).toUpperCase() === "P0").length;
      const p1 = arr.filter((i) => String(i.severity).toUpperCase() === "P1").length;
      const p2 = arr.filter((i) => String(i.severity).toUpperCase() === "P2").length;
      const stats = {
        totalIncidents: arr.length,
        severityCounts: { P0: p0, P1: p1, P2: p2 },
      };

      // Append new time-series snapshot, keep last MAX_GRAPH_POINTS
      const snapshot = buildSnapshot(arr);
      const prev = get().graphData;
      const graphData = [...prev, snapshot].slice(-MAX_GRAPH_POINTS);

      set({ activeIncidents: arr, loading: false, stats, graphData });
      return incidents;
    } catch (e) {
      set({ error: e?.detail ?? "Failed to fetch incidents", loading: false });
      return null;
    }
  },

  fetchIncidentById: async (id) => {
    if (get().loading) return get().selectedIncident;
    set({ loading: true, error: null });
    try {
      const incident = await incidentService.getIncidentById(id);
      set({ selectedIncident: incident, loading: false });
      return incident;
    } catch (e) {
      set({ error: e?.detail ?? "Failed to fetch incident", loading: false });
      return null;
    }
  },

  setSelectedIncident: (incident) => set({ selectedIncident: incident }),
}));
