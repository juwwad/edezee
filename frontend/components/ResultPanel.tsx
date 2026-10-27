"use client";

import type { Diagnostics, Slide } from "@/lib/api";

interface ResultPanelProps {
  slides: Slide[];
  diagnostics: Diagnostics;
  onDownload: () => void;
}

const GROUNDING_LABEL: Record<Slide["grounding"], string> = {
  research: "Web-researched",
  "model-knowledge": "Model knowledge",
  placeholder: "Needs review",
};

const GROUNDING_STYLE: Record<Slide["grounding"], string> = {
  research: "bg-emerald-50 text-emerald-700",
  "model-knowledge": "bg-slate-100 text-slate-600",
  placeholder: "bg-red-50 text-red-600",
};

export default function ResultPanel({ slides, diagnostics, onDownload }: ResultPanelProps) {
  const reviewCount = diagnostics.degraded_slides;

  return (
    <section className="space-y-5">
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold tracking-tight text-slate-900">
              Your presentation is ready
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              {diagnostics.slides_generated} slides ·{" "}
              {(diagnostics.total_latency_ms / 1000).toFixed(1)}s ·{" "}
              {diagnostics.research_used ? "web research on" : "model knowledge only"}
            </p>
          </div>
          <button
            type="button"
            onClick={onDownload}
            className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
          >
            Download .pptx
          </button>
        </div>

        {reviewCount > 0 && (
          <p role="status" className="mt-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-600">
            {reviewCount} slide{reviewCount === 1 ? "" : "s"} could not be generated and need
            review before you teach:{" "}
            <span className="font-medium">{diagnostics.failed_topics.join(", ")}</span>
          </p>
        )}

        {diagnostics.warnings.length > 0 && (
          <ul className="mt-4 space-y-1 text-xs text-slate-500">
            {diagnostics.warnings.map((warning) => (
              <li key={warning}>· {warning}</li>
            ))}
          </ul>
        )}
      </div>

      <div className="space-y-4">
        {slides.map((slide) => (
          <article
            key={`${slide.slide_number}-${slide.topic}`}
            className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
          >
            <header className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-baseline gap-3">
                <span className="text-xs font-semibold tabular-nums text-slate-400">
                  {String(slide.slide_number).padStart(2, "0")}
                </span>
                <h3 className="text-base font-semibold text-slate-900">{slide.slide_title}</h3>
              </div>
              <span
                className={`rounded-full px-2.5 py-1 text-xs font-medium ${GROUNDING_STYLE[slide.grounding]}`}
              >
                {GROUNDING_LABEL[slide.grounding]}
              </span>
            </header>

            <ul className="mt-4 space-y-2">
              {slide.bullet_points.map((bullet, index) => (
                <li key={index} className="flex gap-3 text-sm leading-relaxed text-slate-700">
                  <span aria-hidden="true" className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-blue-500" />
                  <span>{bullet}</span>
                </li>
              ))}
            </ul>

            {slide.speaker_notes && (
              <details className="mt-4 rounded-lg bg-slate-50 px-4 py-3">
                <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Speaker notes
                </summary>
                <p className="mt-2 text-sm leading-relaxed text-slate-600">{slide.speaker_notes}</p>
              </details>
            )}

            {slide.error && (
              <p className="mt-3 text-xs text-red-600">Reason: {slide.error}</p>
            )}

            {slide.sources.length > 0 && (
              <ul className="mt-3 space-y-1">
                {slide.sources.slice(0, 3).map((source) => (
                  <li key={source} className="truncate text-xs text-slate-400">
                    <a
                      href={source}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="underline-offset-2 hover:text-slate-600 hover:underline"
                    >
                      {source}
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
