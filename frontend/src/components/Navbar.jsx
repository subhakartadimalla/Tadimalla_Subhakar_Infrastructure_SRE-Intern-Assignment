import React from "react";

export default function Navbar() {
  return (
    <header className="border-b border-slate-800 bg-slate-950/60 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600 text-white">
            IMS
          </div>
          <div className="leading-tight">
            <div className="text-sm font-semibold text-slate-100">Incident Management System</div>
            <div className="text-xs text-slate-400">Realtime operations dashboard</div>
          </div>
        </div>
        <div className="text-xs text-slate-400">Env: {import.meta.env.MODE}</div>
      </div>
    </header>
  );
}

