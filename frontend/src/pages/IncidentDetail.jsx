import React, { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import Loader from "../components/Loader.jsx";
import * as incidentService from "../services/incidentService.js";
import { useIncidentStore } from "../store/useIncidentStore.js";

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

function formatIso(iso) {
  if (!iso) return "—";
  const ms = Date.parse(iso);
  if (Number.isNaN(ms)) return String(iso);
  return new Date(ms).toLocaleString();
}

function safeString(v) {
  if (v == null) return "";
  if (typeof v === "string") return v;
  try {
    return JSON.stringify(v);
  } catch {
    return String(v);
  }
}

export default function IncidentDetail() {
  const { id } = useParams();
  const { selectedIncident, loading, error, fetchIncidentById, clearError } = useIncidentStore();
  const [actionBusy, setActionBusy] = useState(false);
  const [actionError, setActionError] = useState(null);
  const [expandedSignals, setExpandedSignals] = useState(() => new Set());

  React.useEffect(() => {
    void fetchIncidentById(id);
  }, [id, fetchIncidentById]);

  const detail = selectedIncident;
  // Backend may return either:
  // - flat: { id, component_id, ..., signals: [], rca: ... }
  // - nested: { incident: {...}, signals: [], rca: ... }
  const incident = detail?.incident ?? detail ?? null;
  const signals = Array.isArray(detail?.signals) ? detail.signals : Array.isArray(incident?.signals) ? incident.signals : [];
  const rca = detail?.rca ?? incident?.rca ?? null;

  const status = String(incident?.status ?? "").toUpperCase();
  const allowed = useMemo(() => {
    const hasRca = Boolean(rca && rca.root_cause && rca.fix_applied && rca.prevention_steps);
    return {
      investigating: status === "OPEN",
      resolved: status === "INVESTIGATING",
      closed: status === "RESOLVED" && hasRca,
      hasRca,
    };
  }, [status, rca]);

  async function doTransition(next) {
    if (next === "CLOSED") {
      const ok = window.confirm("Close this incident? Make sure RCA is complete.");
      if (!ok) return;
    }
    setActionBusy(true);
    setActionError(null);
    try {
      await incidentService.transitionIncidentState(id, next);
      await fetchIncidentById(id);
    } catch (e) {
      setActionError(e?.detail ?? "State transition failed");
    } finally {
      setActionBusy(false);
    }
  }

  function toggleExpanded(idx) {
    setExpandedSignals((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-100">Incident Detail</h1>
          <div className="mt-1 font-mono text-xs text-slate-400">{id}</div>
        </div>
        <div className="flex items-center gap-2">
          <button className="ims-btn-ghost" onClick={() => fetchIncidentById(id)}>
            Refresh
          </button>
          <Link className="ims-btn-primary" to={`/incident/${id}/rca`}>
            {rca ? "View/Edit RCA" : "Add RCA"}
          </Link>
        </div>
      </div>

      {loading ? <Loader label="Loading incident…" /> : null}

      {error ? (
        <div className="ims-card border-red-500/30 bg-red-500/10 p-4">
          <div className="text-sm font-semibold text-red-200">Couldn’t load incident</div>
          <div className="mt-1 text-sm text-red-200/80">{String(error)}</div>
          <div className="mt-3">
            <button
              className="ims-btn-primary"
              onClick={() => {
                clearError();
                fetchIncidentById(id);
              }}
            >
              Retry
            </button>
          </div>
        </div>
      ) : null}

      {!loading && !error && incident ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {/* Incident Summary */}
          <section className="ims-card p-4 lg:col-span-2">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-slate-100">Incident Summary</div>
                <div className="mt-1 text-xs text-slate-400">Core details and timestamps</div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className={severityBadgeClass(incident.severity)}>{incident.severity}</span>
                <span className={statusBadgeClass(incident.status)}>{incident.status}</span>
              </div>
            </div>

            <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Component</div>
                <div className="mt-1 truncate text-sm text-slate-100">{incident.component_id}</div>
              </div>
              <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Signals</div>
                <div className="mt-1 text-sm text-slate-100">{incident.signal_count}</div>
              </div>
              <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Created</div>
                <div className="mt-1 text-sm text-slate-100">{formatIso(incident.created_at)}</div>
              </div>
              <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Last updated</div>
                <div className="mt-1 text-sm text-slate-100">{formatIso(incident.updated_at)}</div>
              </div>
              <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">First signal</div>
                <div className="mt-1 text-sm text-slate-100">{formatIso(incident.first_signal_time)}</div>
              </div>
              <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Last signal</div>
                <div className="mt-1 text-sm text-slate-100">{formatIso(incident.last_signal_time)}</div>
              </div>
            </div>
          </section>

          {/* State Controls */}
          <section className="ims-card p-4">
            <div className="text-sm font-semibold text-slate-100">State Controls</div>
            <div className="mt-1 text-xs text-slate-400">Workflow: OPEN → INVESTIGATING → RESOLVED → CLOSED</div>

            {actionError ? (
              <div className="mt-3 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
                {safeString(actionError)}
              </div>
            ) : null}

            <div className="mt-4 space-y-2">
              <button
                className="ims-btn-primary w-full"
                disabled={actionBusy || !allowed.investigating}
                onClick={() => doTransition("INVESTIGATING")}
              >
                Start Investigation
              </button>
              <button
                className="ims-btn-primary w-full"
                disabled={actionBusy || !allowed.resolved}
                onClick={() => doTransition("RESOLVED")}
              >
                Mark Resolved
              </button>
              <button
                className="ims-btn-primary w-full"
                disabled={actionBusy || !allowed.closed}
                onClick={() => doTransition("CLOSED")}
              >
                Close Incident
              </button>
              {!allowed.hasRca && status === "RESOLVED" ? (
                <div className="mt-2 text-xs text-slate-400">
                  Closing requires a completed RCA.{" "}
                  <Link className="text-indigo-300 hover:text-indigo-200" to={`/incident/${id}/rca`}>
                    Add RCA
                  </Link>
                  .
                </div>
              ) : null}
            </div>
          </section>

          {/* Signals */}
          <section className="ims-card p-4 lg:col-span-2">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-slate-100">Signals</div>
                <div className="mt-1 text-xs text-slate-400">All raw signals captured for this incident</div>
              </div>
              <div className="text-xs text-slate-400">{signals.length} total</div>
            </div>

            <div className="mt-4 max-h-[520px] overflow-auto rounded-lg border border-slate-800 bg-slate-950/40">
              {signals.length === 0 ? (
                <div className="p-4 text-sm text-slate-300">No signals captured yet.</div>
              ) : (
                <ul className="divide-y divide-slate-800">
                  {signals.map((s, idx) => {
                    const msg = s?.message ?? s?.msg ?? "(no message)";
                    const ts = s?.timestamp ?? s?.ts ?? null;
                    const expanded = expandedSignals.has(idx);
                    return (
                      <li key={idx} className="p-3 hover:bg-slate-900/40">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="truncate text-sm font-medium text-slate-100">{safeString(msg)}</div>
                            <div className="mt-1 font-mono text-xs text-slate-400">{formatIso(ts)}</div>
                          </div>
                          <button className="ims-btn-ghost shrink-0" onClick={() => toggleExpanded(idx)}>
                            {expanded ? "Hide" : "JSON"}
                          </button>
                        </div>
                        {expanded ? (
                          <pre className="mt-2 overflow-auto rounded-lg bg-slate-950/60 p-3 text-xs text-slate-200">
                            {safeString(s)}
                          </pre>
                        ) : null}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </section>

          {/* RCA */}
          <section className="ims-card p-4 lg:col-span-1">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-slate-100">RCA</div>
                <div className="mt-1 text-xs text-slate-400">Root cause analysis & MTTR</div>
              </div>
              <Link className="ims-btn-ghost" to={`/incident/${id}/rca`}>
                {rca ? "View/Edit RCA" : "Add RCA"}
              </Link>
            </div>

            {rca ? (
              <div className="mt-4 space-y-3">
                <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
                  <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Root cause</div>
                  <div className="mt-1 text-sm text-slate-100 whitespace-pre-wrap">{safeString(rca.root_cause)}</div>
                </div>
                <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
                  <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Fix applied</div>
                  <div className="mt-1 text-sm text-slate-100 whitespace-pre-wrap">{safeString(rca.fix_applied)}</div>
                </div>
                <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
                  <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Prevention</div>
                  <div className="mt-1 text-sm text-slate-100 whitespace-pre-wrap">{safeString(rca.prevention_steps)}</div>
                </div>
                <div className="grid grid-cols-1 gap-3">
                  <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
                    <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Start</div>
                    <div className="mt-1 text-sm text-slate-100">{formatIso(rca.start_time)}</div>
                  </div>
                  <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
                    <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">End</div>
                    <div className="mt-1 text-sm text-slate-100">{formatIso(rca.end_time)}</div>
                  </div>
                  <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
                    <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">MTTR (seconds)</div>
                    <div className="mt-1 text-sm text-slate-100">{safeString(rca.mttr)}</div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="mt-4 rounded-lg border border-slate-800 bg-slate-950/40 p-4 text-sm text-slate-300">
                No RCA submitted yet.
                <div className="mt-2">
                  <Link className="text-indigo-300 hover:text-indigo-200" to={`/incident/${id}/rca`}>
                    Add RCA
                  </Link>
                </div>
              </div>
            )}
          </section>
        </div>
      ) : null}
    </div>
  );
}

