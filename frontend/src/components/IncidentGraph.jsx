import React, { useState, useEffect } from "react";
import {
  ComposedChart,
  LineChart,
  BarChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";

const C = {
  total:   "#818cf8",  // indigo-400
  p0:      "#f87171",  // red-400
  p1:      "#fb923c",  // orange-400
  p2:      "#facc15",  // yellow-400
  newSig:  "#34d399",  // emerald-400
  grid:    "#1e293b",
};

/* ── Shared tooltip ─────────────────────────────────────────────────────── */
function DarkTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs shadow-xl">
      <div className="mb-1.5 font-medium text-slate-300">{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} className="flex items-center gap-2 leading-5">
          <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: p.color }} />
          <span className="text-slate-400">{p.name}:</span>
          <span className="font-semibold text-slate-100">{p.value}</span>
        </div>
      ))}
    </div>
  );
}

/* ── Shared axis config ─────────────────────────────────────────────────── */
const xAxisProps = {
  dataKey: "time",
  tick: { fill: "#64748b", fontSize: 10 },
  axisLine: false,
  tickLine: false,
  interval: "preserveStartEnd",
};

const yAxisProps = {
  allowDecimals: false,
  tick: { fill: "#64748b", fontSize: 10 },
  axisLine: false,
  tickLine: false,
  width: 28,
};

const legendStyle = {
  fontSize: "11px",
  color: "#94a3b8",
  paddingTop: "8px",
};

/* ── Live ticker ─────────────────────────────────────────────────────────── */
function LiveBadge({ dataLen }) {
  const [now, setNow] = useState(() =>
    new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false })
  );
  useEffect(() => {
    const id = setInterval(
      () =>
        setNow(
          new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false })
        ),
      1000
    );
    return () => clearInterval(id);
  }, []);

  return (
    <div className="flex items-center gap-3">
      <span className="flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-400 ring-1 ring-emerald-500/20">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
        Live
      </span>
      <span className="text-xs text-slate-500">
        {now} · {dataLen} point{dataLen !== 1 ? "s" : ""}
      </span>
    </div>
  );
}

/* ── Main component ─────────────────────────────────────────────────────── */
export default function IncidentGraph({ graphData }) {
  const data = Array.isArray(graphData) ? graphData : [];

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 shadow-sm overflow-hidden">

      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800/60 px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-100">
            Signal / Incident Activity
          </h2>
          <p className="mt-0.5 text-xs text-slate-500">
            Rolling {data.length}/{15} snapshots · refreshes every 5 s
          </p>
        </div>
        <LiveBadge dataLen={data.length} />
      </div>

      {/* No-data state */}
      {data.length === 0 ? (
        <div className="flex h-40 items-center justify-center gap-2 text-xs text-slate-500">
          <span className="h-2 w-2 animate-pulse rounded-full bg-slate-600" />
          Waiting for first refresh cycle…
        </div>
      ) : (
        <div className="space-y-0">

          {/* ── Chart 1: Incident counts by severity ───────────────── */}
          <div className="px-4 pt-4">
            <p className="mb-2 text-xs font-medium uppercase tracking-wider text-slate-500">
              Incident Counts
            </p>
            <ResponsiveContainer width="100%" height={160}>
              <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={C.grid} vertical={false} />
                <XAxis {...xAxisProps} />
                <YAxis {...yAxisProps} />
                <Tooltip content={<DarkTooltip />} />
                <Legend iconType="circle" iconSize={7} wrapperStyle={legendStyle} />
                <Line
                  type="monotone"
                  dataKey="total"
                  name="Total"
                  stroke={C.total}
                  strokeWidth={2}
                  dot={{ r: 3, fill: C.total, strokeWidth: 0 }}
                  activeDot={{ r: 5, strokeWidth: 0 }}
                  isAnimationActive={true}
                />
                <Line
                  type="monotone"
                  dataKey="p0"
                  name="P0"
                  stroke={C.p0}
                  strokeWidth={1.5}
                  strokeDasharray="4 2"
                  dot={{ r: 2, fill: C.p0, strokeWidth: 0 }}
                  activeDot={{ r: 4, strokeWidth: 0 }}
                  isAnimationActive={true}
                />
                <Line
                  type="monotone"
                  dataKey="p1"
                  name="P1"
                  stroke={C.p1}
                  strokeWidth={1.5}
                  strokeDasharray="4 2"
                  dot={{ r: 2, fill: C.p1, strokeWidth: 0 }}
                  activeDot={{ r: 4, strokeWidth: 0 }}
                  isAnimationActive={true}
                />
                <Line
                  type="monotone"
                  dataKey="p2"
                  name="P2"
                  stroke={C.p2}
                  strokeWidth={1.5}
                  strokeDasharray="4 2"
                  dot={{ r: 2, fill: C.p2, strokeWidth: 0 }}
                  activeDot={{ r: 4, strokeWidth: 0 }}
                  isAnimationActive={true}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* ── Divider ────────────────────────────────────────────── */}
          <div className="mx-4 border-t border-slate-800/60" />

          {/* ── Chart 2: New signals per interval (bar) ────────────── */}
          <div className="px-4 pb-4 pt-3">
            <p className="mb-2 text-xs font-medium uppercase tracking-wider text-slate-500">
              New Signals per 5 s Interval
            </p>
            <ResponsiveContainer width="100%" height={110}>
              <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={C.grid} vertical={false} />
                <XAxis {...xAxisProps} />
                <YAxis {...yAxisProps} />
                <Tooltip content={<DarkTooltip />} />
                <Bar
                  dataKey="newSignals"
                  name="New signals"
                  fill={C.newSig}
                  radius={[3, 3, 0, 0]}
                  maxBarSize={28}
                  isAnimationActive={true}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>

        </div>
      )}
    </div>
  );
}
