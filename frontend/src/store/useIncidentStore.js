import { create } from "zustand";
import * as incidentService from "../services/incidentService.js";

export const useIncidentStore = create((set, get) => ({
  activeIncidents: [],
  selectedIncident: null,
  loading: false,
  error: null,

  clearError: () => set({ error: null }),

  fetchIncidents: async () => {
    if (get().loading) return get().activeIncidents;
    set({ loading: true, error: null });
    try {
      const incidents = await incidentService.listIncidents();
      set({ activeIncidents: incidents, loading: false });
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

