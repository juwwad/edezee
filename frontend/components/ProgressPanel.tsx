"use client";

import type { ProgressEvent } from "@/lib/api";

interface ProgressPanelProps {
  events: ProgressEvent[];
  elapsedSeconds: number;
  onCancel: () => void;
}

/**
 * Long-running pipelines cause users to abandon a tool they think is broken.
 * This panel shows the current stage, a determinate bar across topics, and a
 * live elapsed timer so waiting feels bounded.
 */
export default function ProgressPanel({ events, elapsedSeconds, onCancel }: ProgressPanelProps) {
  const latest = events[events.length - 1];
  const total = latest?.total ?? 0;
  const completed = latest?.completed ?? 0;
  const percent = total > 0 ? Math.round((completed / total) * 100) : 0;

  return (
    <section
      aria-live="polite"
      aria-busy="true"
      className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-slate-900">Generating your deck</h2>
          <p className="mt-1 text-sm text-slate-600">
            {latest?.message ?? "Starting the pipeline…"}
          </p>
        </div>
        <span className="shrink-0 rounded-full bg-slate-100 px-3 py-1 text-xs font-medium tabular-nums text-slate-600">
          {elapsedSeconds}s
        </span>
      </div>

      <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-slate-100">
        <div
          role="progressbar"
          aria-valuenow={percent}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Generation progress"
          className="h-full rounded-full bg-blue-600 transition-all duration-500"
          style={{ width: `${Math.max(percent, 4)}%` }}
        />
      </div>

      {total > 0 && (
        <p className="mt-2 text-xs tabular-nums text-slate-500">
          {completed} of {total} topics processed
        </p>
      )}

      <ol className="mt-5 space-y-2">
        {events.slice(-4).map((event, index, visible) => (
          <li
            key={`${event.stage}-${index}`}
            className={`flex items-center gap-2 text-sm ${
              index === visible.length - 1 ? "step-active text-slate-900" : "text-slate-500"
            }`}
          >
            <span
              aria-hidden="true"
              className={`h-1.5 w-1.5 rounded-full ${
                index === visible.length - 1 ? "bg-blue-600" : "bg-slate-300"
              }`}
            />
            <span className="truncate">{event.message}</span>
          </li>
        ))}
      </ol>

      <button
        type="button"
        onClick={onCancel}
        className="mt-5 text-sm font-medium text-slate-500 underline-offset-2 hover:text-slate-700 hover:underline focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
      >
        Cancel generation
      </button>
    </section>
  );
}
