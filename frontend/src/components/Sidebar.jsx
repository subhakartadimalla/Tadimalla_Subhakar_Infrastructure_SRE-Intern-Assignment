import React from "react";
import { NavLink } from "react-router-dom";

function LinkItem({ to, label }) {
  return (
    <NavLink
      to={to}
      end={to === "/"}
      className={({ isActive }) =>
        [
          "block rounded-lg px-3 py-2 text-sm font-medium",
          isActive ? "bg-slate-800/70 text-white" : "text-slate-300 hover:bg-slate-900/60",
        ].join(" ")
      }
    >
      {label}
    </NavLink>
  );
}

export default function Sidebar() {
  return (
    <aside className="hidden w-60 shrink-0 md:block">
      <div className="ims-card p-3">
        <div className="px-2 pb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
          Navigation
        </div>
        <nav className="space-y-1">
          <LinkItem to="/" label="Dashboard" />
          <LinkItem to="/" label="Incidents" />
        </nav>
      </div>
      <div className="mt-4 ims-card p-3">
        <div className="text-xs text-slate-400">
          API Base URL:{" "}
          <span className="font-mono text-slate-200">{import.meta.env.VITE_API_BASE_URL ?? "(unset)"}</span>
        </div>
      </div>
    </aside>
  );
}

