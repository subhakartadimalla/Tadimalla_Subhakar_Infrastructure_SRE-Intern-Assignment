import { create } from "zustand";
import * as incidentService from "../services/incidentService.js";

const MAX_GRAPH_POINTS = 15;

function buildSnapshot(incidents, prevSignalTotal) {
  const arr = Array.isArray(incidents) ? incidents : [];
  const p0 = arr.filter((i) => String(i.severity).toUpperCase() === "P0").length;
  const p1 = arr.filter((i) => String(i.severity).toUpperCase() === "P1").length;
  const p2 = arr.filter((i) => String(i.severity).toUpperCase() === "P2").length;
  const totalSignals = arr.reduce((sum, i) => sum + (Number(i.signal_count) || 0), 0);

  // newSignals = signals received since last snapshot — always shows activity
  const newSignals = Math.max(0, totalSignals - (prevSignalTotal ?? totalSignals));

  const time = new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });

  return { time, total: arr.length, p0, p1, p2, totalSignals, newSignals };
}

export const useIncidentStore = create((set, get) => ({
  activeIncidents: [],
  selectedIncident: null,

  // Separate loading flags — detail-page loads never block dashboard refresh
  loadingList: false,
  loadingDetail: false,
  loading: false, // unified alias for backward-compat

  error: null,

  stats: {
    totalIncidents: 0,
    severityCounts: { P0: 0, P1: 0, P2: 0 },
  },

  // Rolling time-series, max MAX_GRAPH_POINTS — always appended, never replaced
  graphData: [],

  clearError: () => set({ error: null }),

  fetchIncidents: async () => {
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

      // Functional set — reads latest graphData, never a stale closure
      set((state) => {
        const prevSignalTotal =
          state.graphData.length > 0
            ? state.graphData[state.graphData.length - 1].totalSignals
            : undefined;

        const snapshot = buildSnapshot(arr, prevSignalTotal);
        const graphData = [...state.graphData, snapshot].slice(-MAX_GRAPH_POINTS);

        console.log(
          `[IMS] graph tick #${graphData.length} | total=${snapshot.total} p0=${snapshot.p0} p1=${snapshot.p1} p2=${snapshot.p2} newSignals=${snapshot.newSignals}`
        );

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
