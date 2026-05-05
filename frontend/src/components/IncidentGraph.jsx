import React from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

const COLORS = {
  total:   "#818cf8",   // indigo-400
  p0:      "#f87171",   // red-400
  p1:      "#fb923c",   // orange-400
  p2:      "#facc15",   // yellow-400
  signals: "#34d399",   // emerald-400
};

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs shadow-lg">
      <div className="mb-1 font-medium text-slate-300">{label}</div>
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

export default function IncidentGraph({ graphData }) {
  const data = Array.isArray(graphData) ? graphData : [];
  const hasData = data.length >= 2; // need ≥2 points to draw a line

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4 shadow-sm">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-slate-100">
            Signal / Incident Activity
          </h2>
          <p className="mt-0.5 text-xs text-slate-500">
            {data.length < 2
              ? `Collecting data — ${data.length}/2 points needed to draw lines`
              : `Last ${data.length} refresh cycles · updates every 5 s`}
          </p>
        </div>
        <span className="flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-400 ring-1 ring-emerald-500/20">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
          Live
        </span>
      </div>

      {/* Axis legend */}
      <div className="mb-2 flex items-center justify-end gap-4 text-xs text-slate-500">
        <span className="flex items-center gap-1">
          <span className="inline-block h-px w-4 bg-indigo-400" /> Incidents (left axis)
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-px w-4 bg-emerald-400" /> Signals (right axis)
        </span>
      </div>

      {/* Loading / empty state */}
      {!hasData ? (
        <div className="flex h-44 items-center justify-center">
          <div className="text-center">
            <div className="text-xs text-slate-500">
              {data.length === 0
                ? "Waiting for first refresh cycle…"
                : "One more refresh cycle to draw lines…"}
            </div>
            <div className="mt-2 flex justify-center gap-1">
              {[0, 1, 2].map((i) => (
                <span
                  key={i}
                  className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-600"
                  style={{ animationDelay: `${i * 0.15}s` }}
                />
              ))}
            </div>
          </div>
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <LineChart
            data={data}
            margin={{ top: 4, right: 48, bottom: 0, left: -8 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#1e293b"
              vertical={false}
            />

            {/* Left Y-axis: incident counts (whole numbers, small range) */}
            <YAxis
              yAxisId="incidents"
              orientation="left"
              allowDecimals={false}
              tick={{ fill: "#64748b", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              width={28}
            />

            {/* Right Y-axis: total signal count (larger numbers) */}
            <YAxis
              yAxisId="signals"
              orientation="right"
              allowDecimals={false}
              tick={{ fill: "#34d399", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              width={40}
            />

            <XAxis
              dataKey="time"
              tick={{ fill: "#64748b", fontSize: 10 }}
              axisLine={false}
              tickLine={false}
              interval="preserveStartEnd"
            />

            <Tooltip content={<CustomTooltip />} />

            <Legend
              iconType="circle"
              iconSize={8}
              wrapperStyle={{
                fontSize: "11px",
                color: "#94a3b8",
                paddingTop: "10px",
              }}
            />

            {/* Incident count lines — left axis */}
            <Line
              yAxisId="incidents"
              type="monotone"
              dataKey="total"
              name="Total"
              stroke={COLORS.total}
              strokeWidth={2}
              dot={{ r: 3, fill: COLORS.total, strokeWidth: 0 }}
              activeDot={{ r: 5, strokeWidth: 0 }}
              isAnimationActive={false}
            />
            <Line
              yAxisId="incidents"
              type="monotone"
              dataKey="p0"
              name="P0"
              stroke={COLORS.p0}
              strokeWidth={1.5}
              strokeDasharray="4 2"
              dot={{ r: 2, fill: COLORS.p0, strokeWidth: 0 }}
              activeDot={{ r: 4, strokeWidth: 0 }}
              isAnimationActive={false}
            />
            <Line
              yAxisId="incidents"
              type="monotone"
              dataKey="p1"
              name="P1"
              stroke={COLORS.p1}
              strokeWidth={1.5}
              strokeDasharray="4 2"
              dot={{ r: 2, fill: COLORS.p1, strokeWidth: 0 }}
              activeDot={{ r: 4, strokeWidth: 0 }}
              isAnimationActive={false}
            />
            <Line
              yAxisId="incidents"
              type="monotone"
              dataKey="p2"
              name="P2"
              stroke={COLORS.p2}
              strokeWidth={1.5}
              strokeDasharray="4 2"
              dot={{ r: 2, fill: COLORS.p2, strokeWidth: 0 }}
              activeDot={{ r: 4, strokeWidth: 0 }}
              isAnimationActive={false}
            />

            {/* Signal count line — right axis */}
            <Line
              yAxisId="signals"
              type="monotone"
              dataKey="signals"
              name="Signals"
              stroke={COLORS.signals}
              strokeWidth={2}
              dot={{ r: 3, fill: COLORS.signals, strokeWidth: 0 }}
              activeDot={{ r: 5, strokeWidth: 0 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
