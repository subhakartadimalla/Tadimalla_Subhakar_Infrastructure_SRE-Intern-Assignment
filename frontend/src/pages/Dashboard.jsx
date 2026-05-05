import React, { useEffect, useMemo, useRef } from "react";
import IncidentCard from "../components/IncidentCard.jsx";
import Loader from "../components/Loader.jsx";
import StatsCards from "../components/StatsCards.jsx";
import IncidentGraph from "../components/IncidentGraph.jsx";
import { useIncidentStore } from "../store/useIncidentStore.js";

function severityRank(sev) {
  const s = String(sev || "").toUpperCase();
  if (s === "P0") return 0;
  if (s === "P1") return 1;
  if (s === "P2") return 2;
  return 9;
}

function updatedAtMs(incident) {
  const v = incident?.last_updated ?? incident?.updated_at ?? incident?.updatedAt;
  const ms = typeof v === "string" ? Date.parse(v) : NaN;
  return Number.isNaN(ms) ? 0 : ms;
}

export default function Dashboard() {
  const {
    activeIncidents,
    loading,
    error,
    fetchIncidents,
    clearError,
    stats,
    graphData,
  } = useIncidentStore();

  const intervalRef = useRef(null);

  useEffect(() => {
    void fetchIncidents();
  }, [fetchIncidents]);

  useEffect(() => {
    intervalRef.current = setInterval(() => {
      void fetchIncidents();
    }, 5000);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
      intervalRef.current = null;
    };
  }, [fetchIncidents]);

  const sortedIncidents = useMemo(() => {
    const items = Array.isArray(activeIncidents) ? [...activeIncidents] : [];
    items.sort((a, b) => {
      const sr = severityRank(a?.severity) - severityRank(b?.severity);
      if (sr !== 0) return sr;
      return updatedAtMs(b) - updatedAtMs(a);
    });
    return items;
  }, [activeIncidents]);

  return (
    <div className="space-y-5">

      {/* Page header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-slate-100">Dashboard</h1>
          <p className="mt-1 text-sm text-slate-400">
            Live active incidents — auto-refresh every 5s
          </p>
        </div>
        <button className="ims-btn-primary" onClick={() => fetchIncidents()}>
          Refresh
        </button>
      </div>

      {/* Stats cards */}
      <StatsCards stats={stats} />

      {/* Activity graph */}
      <IncidentGraph graphData={graphData} />

      {/* Divider */}
      <div className="flex items-center gap-3">
        <div className="h-px flex-1 bg-slate-800" />
        <span className="text-xs font-medium uppercase tracking-widest text-slate-600">
          Active Incidents
        </span>
        <div className="h-px flex-1 bg-slate-800" />
      </div>

      {/* Error banner */}
      {error ? (
        <div className="ims-card border-red-500/30 bg-red-500/10 p-4">
          <div className="text-sm font-semibold text-red-200">Couldn't load incidents</div>
          <div className="mt-1 text-sm text-red-200/80">{error}</div>
          <div className="mt-3 flex gap-2">
            <button
              className="ims-btn-primary"
              onClick={() => {
                clearError();
                fetchIncidents();
              }}
            >
              Retry
            </button>
          </div>
        </div>
      ) : null}

      {loading && sortedIncidents.length === 0 ? (
        <Loader label="Fetching incidents…" />
      ) : null}

      {!loading && !error && sortedIncidents.length === 0 ? (
        <div className="ims-card p-6 text-sm text-slate-300">
          No active incidents yet. Send signals to create incidents.
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        {sortedIncidents.map((inc) => (
          <IncidentCard key={inc.id} incident={inc} />
        ))}
      </div>
    </div>
  );
}
