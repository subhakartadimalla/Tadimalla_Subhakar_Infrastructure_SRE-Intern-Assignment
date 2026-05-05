import React from "react";
import { Link } from "react-router-dom";

function severityBadgeClass(severity) {
  const s = String(severity || "").toUpperCase();
  if (s === "P0") return "ims-badge bg-red-500/15 text-red-300 ring-1 ring-red-500/30";
  if (s === "P1") return "ims-badge bg-orange-500/15 text-orange-300 ring-1 ring-orange-500/30";
  if (s === "P2") return "ims-badge bg-yellow-500/15 text-yellow-200 ring-1 ring-yellow-500/30";
  return "ims-badge bg-slate-500/15 text-slate-200 ring-1 ring-slate-500/30";
}

function statusBadgeClass(status) {
  const v = String(status || "").toUpperCase();
  if (v === "OPEN") return "ims-badge bg-sky-500/15 text-sky-300 ring-1 ring-sky-500/30";
  if (v === "INVESTIGATING") return "ims-badge bg-indigo-500/15 text-indigo-300 ring-1 ring-indigo-500/30";
  if (v === "RESOLVED") return "ims-badge bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30";
  if (v === "CLOSED") return "ims-badge bg-slate-500/15 text-slate-300 ring-1 ring-slate-500/30";
  return "ims-badge bg-slate-500/15 text-slate-200 ring-1 ring-slate-500/30";
}

function formatLastUpdated(value) {
  if (!value) return "—";
  const ms = Date.parse(value);
  if (Number.isNaN(ms)) return String(value);
  const diffS = Math.max(0, Math.floor((Date.now() - ms) / 1000));
  if (diffS < 60) return `${diffS}s ago`;
  const diffM = Math.floor(diffS / 60);
  if (diffM < 60) return `${diffM}m ago`;
  const diffH = Math.floor(diffM / 60);
  if (diffH < 24) return `${diffH}h ago`;
  const diffD = Math.floor(diffH / 24);
  return `${diffD}d ago`;
}

export default function IncidentCard({ incident }) {
  if (!incident) return null;

  const id = incident.id;
  const lastUpdated = incident.last_updated ?? incident.updated_at ?? incident.updatedAt;
  return (
    <Link
      to={`/incident/${id}`}
      className="ims-card block p-4 transition hover:border-slate-700 hover:bg-slate-900/70"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-slate-100">{incident.component_id}</div>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <span className={severityBadgeClass(incident.severity)}>{incident.severity}</span>
            <span className={statusBadgeClass(incident.status)}>{incident.status}</span>
            <span className="text-xs text-slate-400">signals: {incident.signal_count}</span>
          </div>
          <div className="mt-2 text-xs text-slate-400">
            last updated: <span className="text-slate-200">{formatLastUpdated(lastUpdated)}</span>
          </div>
        </div>

        <div className="shrink-0 text-xs text-slate-400">→</div>
      </div>
    </Link>
  );
}

