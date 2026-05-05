import React, { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import Loader from "../components/Loader.jsx";
import * as incidentService from "../services/incidentService.js";

function toDatetimeLocal(isoValue) {
  if (!isoValue) return "";
  const ms = Date.parse(isoValue);
  if (Number.isNaN(ms)) return "";
  const d = new Date(ms);
  const pad = (n) => String(n).padStart(2, "0");
  const yyyy = d.getFullYear();
  const mm = pad(d.getMonth() + 1);
  const dd = pad(d.getDate());
  const hh = pad(d.getHours());
  const min = pad(d.getMinutes());
  return `${yyyy}-${mm}-${dd}T${hh}:${min}`;
}

function toIso(localValue) {
  if (!localValue) return "";
  const d = new Date(localValue);
  if (Number.isNaN(d.getTime())) return "";
  return d.toISOString();
}

function normalizeError(err) {
  const detail = err?.detail ?? err?.message ?? "Request failed";
  if (typeof detail === "string") return detail;
  try {
    return JSON.stringify(detail);
  } catch {
    return String(detail);
  }
}

export default function RCAForm() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [existingRca, setExistingRca] = useState(null);

  React.useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setLoadError(null);
      try {
        const rca = await incidentService.getRCA(id);
        if (!cancelled) setExistingRca(rca);
      } catch (err) {
        // 404 means no RCA yet; any other error should be shown.
        if (err?.status === 404) {
          if (!cancelled) setExistingRca(null);
        } else if (!cancelled) {
          setLoadError(normalizeError(err));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [id]);

  const initial = useMemo(() => {
    const defaultStartIso = new Date(Date.now() - 60 * 60 * 1000).toISOString();
    const defaultEndIso = new Date().toISOString();
    return {
      root_cause: existingRca?.root_cause ?? "",
      fix_applied: existingRca?.fix_applied ?? "",
      prevention_steps: existingRca?.prevention_steps ?? "",
      start_time: toDatetimeLocal(existingRca?.start_time ?? defaultStartIso),
      end_time: toDatetimeLocal(existingRca?.end_time ?? defaultEndIso),
    };
  }, [existingRca]);

  const [form, setForm] = useState(initial);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [submitSuccess, setSubmitSuccess] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});

  // Keep form in sync after fetch resolves.
  React.useEffect(() => setForm(initial), [initial]);

  function validate(values) {
    const errs = {};
    if (!values.start_time) errs.start_time = "Start time is required";
    if (!values.end_time) errs.end_time = "End time is required";
    if (!values.root_cause?.trim()) errs.root_cause = "Root cause is required";
    if (!values.fix_applied?.trim()) errs.fix_applied = "Fix applied is required";
    if (!values.prevention_steps?.trim()) errs.prevention_steps = "Prevention steps are required";

    if (values.start_time && values.end_time) {
      const startMs = Date.parse(values.start_time);
      const endMs = Date.parse(values.end_time);
      if (!Number.isNaN(startMs) && !Number.isNaN(endMs) && endMs <= startMs) {
        errs.end_time = "End time must be after start time";
      }
    }
    return errs;
  }

  async function onSubmit(e) {
    e.preventDefault();
    if (submitting) return;
    const errs = validate(form);
    setFieldErrors(errs);
    if (Object.keys(errs).length > 0) return;

    setSubmitting(true);
    setSubmitError(null);
    setSubmitSuccess(null);
    try {
      await incidentService.submitRCA(id, {
        root_cause: form.root_cause.trim(),
        fix_applied: form.fix_applied.trim(),
        prevention_steps: form.prevention_steps.trim(),
        start_time: toIso(form.start_time),
        end_time: toIso(form.end_time),
      });
      setSubmitSuccess("RCA submitted successfully. Redirecting to incident detail...");
      setTimeout(() => navigate(`/incident/${id}`), 700);
    } catch (err) {
      setSubmitError(normalizeError(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-100">Submit RCA</h1>
          <div className="mt-1 font-mono text-xs text-slate-400">{id}</div>
        </div>
        <Link className="ims-btn-ghost" to={`/incident/${id}`}>
          Back to incident
        </Link>
      </div>

      {loading ? <Loader label="Loading RCA…" /> : null}

      {loadError ? (
        <div className="ims-card border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
          Couldn’t load RCA: {loadError}
        </div>
      ) : null}

      <form onSubmit={onSubmit} className="ims-card p-4">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <label className="block">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Root cause</div>
            <textarea
              className="mt-2 w-full rounded-lg border border-slate-800 bg-slate-950/50 p-3 text-sm outline-none focus:border-indigo-500"
              rows={4}
              value={form.root_cause}
              onChange={(e) => {
                setFieldErrors((prev) => ({ ...prev, root_cause: undefined }));
                setForm((f) => ({ ...f, root_cause: e.target.value }));
              }}
              required
            />
            {fieldErrors.root_cause ? <div className="mt-1 text-xs text-red-300">{fieldErrors.root_cause}</div> : null}
          </label>

          <label className="block">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Fix applied</div>
            <textarea
              className="mt-2 w-full rounded-lg border border-slate-800 bg-slate-950/50 p-3 text-sm outline-none focus:border-indigo-500"
              rows={4}
              value={form.fix_applied}
              onChange={(e) => {
                setFieldErrors((prev) => ({ ...prev, fix_applied: undefined }));
                setForm((f) => ({ ...f, fix_applied: e.target.value }));
              }}
              required
            />
            {fieldErrors.fix_applied ? <div className="mt-1 text-xs text-red-300">{fieldErrors.fix_applied}</div> : null}
          </label>

          <label className="block lg:col-span-2">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Prevention steps</div>
            <textarea
              className="mt-2 w-full rounded-lg border border-slate-800 bg-slate-950/50 p-3 text-sm outline-none focus:border-indigo-500"
              rows={4}
              value={form.prevention_steps}
              onChange={(e) => {
                setFieldErrors((prev) => ({ ...prev, prevention_steps: undefined }));
                setForm((f) => ({ ...f, prevention_steps: e.target.value }));
              }}
              required
            />
            {fieldErrors.prevention_steps ? (
              <div className="mt-1 text-xs text-red-300">{fieldErrors.prevention_steps}</div>
            ) : null}
          </label>

          <label className="block">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Start time (UTC)</div>
            <input
              type="datetime-local"
              className="mt-2 w-full rounded-lg border border-slate-800 bg-slate-950/50 p-2 text-sm outline-none focus:border-indigo-500"
              value={form.start_time}
              onChange={(e) => {
                setFieldErrors((prev) => ({ ...prev, start_time: undefined, end_time: undefined }));
                setForm((f) => ({ ...f, start_time: e.target.value }));
              }}
              required
            />
            {fieldErrors.start_time ? <div className="mt-1 text-xs text-red-300">{fieldErrors.start_time}</div> : null}
          </label>

          <label className="block">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">End time (UTC)</div>
            <input
              type="datetime-local"
              className="mt-2 w-full rounded-lg border border-slate-800 bg-slate-950/50 p-2 text-sm outline-none focus:border-indigo-500"
              value={form.end_time}
              onChange={(e) => {
                setFieldErrors((prev) => ({ ...prev, end_time: undefined }));
                setForm((f) => ({ ...f, end_time: e.target.value }));
              }}
              required
            />
            {fieldErrors.end_time ? <div className="mt-1 text-xs text-red-300">{fieldErrors.end_time}</div> : null}
          </label>
        </div>

        {submitSuccess ? (
          <div className="mt-4 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-200">
            {submitSuccess}
          </div>
        ) : null}

        {submitError ? (
          <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
            {submitError}
          </div>
        ) : null}

        <div className="mt-5 flex items-center justify-end gap-2">
          <button type="button" className="ims-btn-ghost" onClick={() => setForm(initial)} disabled={submitting}>
            Reset
          </button>
          <button type="submit" className="ims-btn-primary" disabled={submitting}>
            {submitting ? "Submitting…" : existingRca ? "Update RCA" : "Submit RCA"}
          </button>
        </div>
      </form>
    </div>
  );
}

