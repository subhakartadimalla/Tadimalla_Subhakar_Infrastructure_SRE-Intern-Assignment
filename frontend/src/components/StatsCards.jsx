import React from "react";

const CARDS = [
  {
    key: "total",
    label: "Active Incidents",
    description: "Non-closed",
    border: "border-slate-700",
    bg: "bg-slate-800/50",
    numColor: "text-slate-100",
    dot: "bg-slate-400",
  },
  {
    key: "p0",
    label: "P0 Critical",
    description: "Immediate action",
    border: "border-red-500/30",
    bg: "bg-red-500/10",
    numColor: "text-red-300",
    dot: "bg-red-400",
  },
  {
    key: "p1",
    label: "P1 High",
    description: "Urgent",
    border: "border-orange-500/30",
    bg: "bg-orange-500/10",
    numColor: "text-orange-300",
    dot: "bg-orange-400",
  },
  {
    key: "p2",
    label: "P2 Medium",
    description: "Monitor",
    border: "border-yellow-500/30",
    bg: "bg-yellow-500/10",
    numColor: "text-yellow-200",
    dot: "bg-yellow-400",
  },
];

export default function StatsCards({ stats }) {
  const values = {
    total: stats?.totalIncidents ?? 0,
    p0: stats?.severityCounts?.P0 ?? 0,
    p1: stats?.severityCounts?.P1 ?? 0,
    p2: stats?.severityCounts?.P2 ?? 0,
  };

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {CARDS.map((card) => (
        <div
          key={card.key}
          className={`rounded-xl border ${card.border} ${card.bg} p-4 shadow-sm`}
        >
          <div className="flex items-center gap-2">
            <span className={`h-2 w-2 rounded-full ${card.dot}`} />
            <span className="text-xs font-medium uppercase tracking-wide text-slate-400">
              {card.label}
            </span>
          </div>
          <div className={`mt-3 text-3xl font-bold tabular-nums ${card.numColor}`}>
            {values[card.key]}
          </div>
          <div className="mt-1 text-xs text-slate-500">{card.description}</div>
        </div>
      ))}
    </div>
  );
}
