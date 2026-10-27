"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import ProgressPanel from "@/components/ProgressPanel";
import ResultPanel from "@/components/ResultPanel";
import SyllabusForm from "@/components/SyllabusForm";
import {
  ApiError,
  checkHealth,
  downloadBlob,
  generateDeckStream,
  type Depth,
  type Diagnostics,
  type HealthResponse,
  type ProgressEvent,
  type Slide,
} from "@/lib/api";

type Phase = "idle" | "running" | "done" | "error";

interface RunState {
  slides: Slide[];
  diagnostics: Diagnostics | null;
  blob: Blob | null;
  filename: string;
}

const EMPTY_RUN: RunState = { slides: [], diagnostics: null, blob: null, filename: "" };

export default function HomePage() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [run, setRun] = useState<RunState>(EMPTY_RUN);
  const [health, setHealth] = useState<HealthResponse | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    checkHealth(controller.signal)
      .then(setHealth)
      .catch(() => setHealth(null));
    return () => controller.abort();
  }, []);

  const stopTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  useEffect(() => stopTimer, [stopTimer]);

  const handleSubmit = useCallback(
    async (values: { syllabusText: string; depth: Depth; deckTitle: string }) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setPhase("running");
      setEvents([]);
      setElapsed(0);
      setError(null);
      setRun(EMPTY_RUN);

      timerRef.current = setInterval(() => setElapsed((value) => value + 1), 1000);

      try {
        const result = await generateDeckStream({
          ...values,
          signal: controller.signal,
          onProgress: (event) => setEvents((previous) => [...previous, event]),
        });
        setRun({
          slides: result.slides,
          diagnostics: result.diagnostics,
          blob: result.blob,
          filename: result.filename,
        });
        setPhase("done");
      } catch (caught) {
        if (controller.signal.aborted) {
          setPhase("idle");
          setError("Generation cancelled.");
        } else {
          setPhase("error");
          setError(
            caught instanceof ApiError
              ? caught.message
              : "Something went wrong while generating the deck. Please try again.",
          );
        }
      } finally {
        stopTimer();
      }
    },
    [stopTimer],
  );

  const handleCancel = useCallback(() => {
    abortRef.current?.abort();
    stopTimer();
  }, [stopTimer]);

  const handleDownload = useCallback(() => {
    if (run.blob) {
      downloadBlob(run.blob, run.filename);
    }
  }, [run]);

  const busy = phase === "running";
  const ready = health?.llm_configured === true;

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <header className="mb-10">
        <p className="text-xs font-semibold uppercase tracking-widest text-blue-600">Edezee</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-900">
          Syllabus in, slides out
        </h1>
        <p className="mt-3 text-base leading-relaxed text-slate-600">
          Paste your course topics. Edezee researches each one, drafts the slide content, and
          returns a PowerPoint file with speaker notes — ready to teach.
        </p>
      </header>

      {health && !ready && (
        <p role="alert" className="mb-6 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-600">
          The slide generator is not configured on the server. Ask your administrator to set the
          model API key, then reload this page.
        </p>
      )}

      {phase === "error" && error && (
        <p role="alert" className="mb-6 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-600">
          {error}
        </p>
      )}

      {phase === "done" && run.diagnostics && (
        <ResultPanel slides={run.slides} diagnostics={run.diagnostics} onDownload={handleDownload} />
      )}

      {busy && <ProgressPanel events={events} elapsedSeconds={elapsed} onCancel={handleCancel} />}

      {phase !== "done" && phase !== "running" && (
        <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <SyllabusForm busy={busy} onSubmit={handleSubmit} />
        </section>
      )}

      {phase === "done" && (
        <button
          type="button"
          onClick={() => {
            setPhase("idle");
            setRun(EMPTY_RUN);
            setError(null);
          }}
          className="mt-8 w-full rounded-lg border border-slate-300 bg-white px-6 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
        >
          Generate another deck
        </button>
      )}

      <footer className="mt-12 border-t border-slate-200 pt-6 text-xs leading-relaxed text-slate-500">
        <p>
          Always review generated slides before teaching. Each slide shows whether its content was
          web-researched, drawn from model knowledge, or flagged for review.
        </p>
      </footer>
    </main>
  );
}
