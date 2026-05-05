import { create } from "zustand";
import * as incidentService from "../services/incidentService.js";

const MAX_GRAPH_POINTS = 10;

function buildSnapshot(incidents) {
  const arr = Array.isArray(incidents) ? incidents : [];
  const p0 = arr.filter((i) => String(i.severity).toUpperCase() === "P0").length;
  const p1 = arr.filter((i) => String(i.severity).toUpperCase() === "P1").length;
  const p2 = arr.filter((i) => String(i.severity).toUpperCase() === "P2").length;
  const signals = arr.reduce((sum, i) => sum + (Number(i.signal_count) || 0), 0);
  // Unique time label so Recharts always sees new data keys
  const time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
  return { time, total: arr.length, p0, p1, p2, signals };
}

export const useIncidentStore = create((set, get) => ({
  activeIncidents: [],
  selectedIncident: null,

  // Separate loading flags so detail-page fetches never block the dashboard refresh
  loadingList: false,
  loadingDetail: false,

  // Keep a unified `loading` alias for backward compatibility (IncidentDetail still reads it)
  loading: false,

  error: null,

  stats: {
    totalIncidents: 0,
    severityCounts: { P0: 0, P1: 0, P2: 0 },
  },

  // Rolling time-series for the graph — always append, never replace
  graphData: [],

  clearError: () => set({ error: null }),

  fetchIncidents: async () => {
    // Use dedicated loadingList flag — never blocked by detail-page fetches
    if (get().loadingList) return get().activeIncidents;
    set({ loadingList: true, error: null });
    try {
      const incidents = await incidentService.listIncidents();
      const arr = Array.isArray(incidents) ? incidents : [];

      const p0 = arr.filter((i) => String(i.severity).toUpperCase() === "P0").length;
      const p1 = arr.filter((i) => String(i.severity).toUpperCase() === "P1").length;
      const p2 = arr.filter((i) => String(i.severity).toUpperCase() === "P2").length;

      const stats = {
        totalIncidents: arr.length,
        severityCounts: { P0: p0, P1: p1, P2: p2 },
      };

      const snapshot = buildSnapshot(arr);

      // Functional set — always reads latest state, never a stale closure
      set((state) => {
        const graphData = [...state.graphData, snapshot].slice(-MAX_GRAPH_POINTS);
        console.log("[IMS] Graph snapshot appended:", snapshot, "| total points:", graphData.length);
        return {
          activeIncidents: arr,
          loadingList: false,
          loading: false,
          stats,
          graphData,
        };
      });

      return incidents;
    } catch (e) {
      set({ error: e?.detail ?? "Failed to fetch incidents", loadingList: false, loading: false });
      return null;
    }
  },

  fetchIncidentById: async (id) => {
    if (get().loadingDetail) return get().selectedIncident;
    set({ loadingDetail: true, loading: true, error: null });
    try {
      const incident = await incidentService.getIncidentById(id);
      set({ selectedIncident: incident, loadingDetail: false, loading: false });
      return incident;
    } catch (e) {
      set({ error: e?.detail ?? "Failed to fetch incident", loadingDetail: false, loading: false });
      return null;
    }
  },

  setSelectedIncident: (incident) => set({ selectedIncident: incident }),
}));
