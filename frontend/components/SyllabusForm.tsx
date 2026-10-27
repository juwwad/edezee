"use client";

import { useState } from "react";
import type { Depth } from "@/lib/api";

interface SyllabusFormProps {
  busy: boolean;
  onSubmit: (values: { syllabusText: string; depth: Depth; deckTitle: string }) => void;
}

const DEPTH_OPTIONS: Array<{
  value: Depth;
  label: string;
  hint: string;
}> = [
  {
    value: "High-Level",
    label: "High-level overview",
    hint: "Plain-language definitions for a first-time learner.",
  },
  {
    value: "In-Depth",
    label: "In-depth technical",
    hint: "Precise terminology and mechanism-level detail.",
  },
];

const SAMPLE_SYLLABUS = `1. What is retrieval-augmented generation (RAG)?
2. Vector embeddings and similarity search
3. Chunking strategies for documents
4. Evaluating answer faithfulness`;

export default function SyllabusForm({ busy, onSubmit }: SyllabusFormProps) {
  const [syllabusText, setSyllabusText] = useState("");
  const [deckTitle, setDeckTitle] = useState("");
  const [depth, setDepth] = useState<Depth>("High-Level");
  const [localError, setLocalError] = useState<string | null>(null);

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!syllabusText.trim()) {
      setLocalError("Add at least one syllabus topic before generating.");
      return;
    }
    setLocalError(null);
    onSubmit({ syllabusText, depth, deckTitle: deckTitle.trim() });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6" noValidate>
      <div>
        <label htmlFor="deck-title" className="block text-sm font-medium text-slate-700">
          Deck title <span className="font-normal text-slate-500">(optional)</span>
        </label>
        <input
          id="deck-title"
          type="text"
          value={deckTitle}
          onChange={(event) => setDeckTitle(event.target.value)}
          disabled={busy}
          maxLength={200}
          placeholder="Introduction to Retrieval-Augmented Generation"
          className="mt-2 w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-slate-900 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-slate-100 disabled:text-slate-500"
        />
      </div>

      <div>
        <label htmlFor="syllabus" className="block text-sm font-medium text-slate-700">
          Syllabus topics
        </label>
        <p className="mt-1 text-sm text-slate-500">
          Paste one topic per line. Numbering, bullets and week headers are all fine.
        </p>
        <textarea
          id="syllabus"
          rows={10}
          value={syllabusText}
          onChange={(event) => setSyllabusText(event.target.value)}
          disabled={busy}
          aria-describedby="syllabus-help"
          placeholder={"1. What is Next.js?\n2. Server vs. client components\n3. Data fetching strategies"}
          className="mt-2 w-full resize-y rounded-lg border border-slate-300 bg-white px-4 py-3 font-mono text-sm leading-relaxed text-slate-900 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-slate-100 disabled:text-slate-500"
        />
        <div className="mt-2 flex items-center justify-between">
          <span id="syllabus-help" className="text-xs text-slate-500">
            Up to 40 topics per deck.
          </span>
          <button
            type="button"
            onClick={() => setSyllabusText(SAMPLE_SYLLABUS)}
            disabled={busy}
            className="text-xs font-medium text-blue-600 underline-offset-2 hover:underline focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:text-slate-400"
          >
            Use a sample syllabus
          </button>
        </div>
      </div>

      <fieldset disabled={busy} className="space-y-3">
        <legend className="text-sm font-medium text-slate-700">Depth</legend>
        <div className="grid gap-3 sm:grid-cols-2">
          {DEPTH_OPTIONS.map((option) => {
            const selected = depth === option.value;
            return (
              <label
                key={option.value}
                className={`cursor-pointer rounded-xl border p-4 transition ${
                  selected
                    ? "border-blue-600 bg-blue-50 ring-1 ring-blue-600"
                    : "border-slate-200 bg-white hover:border-slate-300"
                } ${busy ? "cursor-not-allowed opacity-70" : ""}`}
              >
                <span className="flex items-center gap-3">
                  <input
                    type="radio"
                    name="depth"
                    value={option.value}
                    checked={selected}
                    onChange={() => setDepth(option.value)}
                    className="h-4 w-4 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm font-semibold text-slate-900">{option.label}</span>
                </span>
                <span className="mt-2 block text-xs leading-relaxed text-slate-500">
                  {option.hint}
                </span>
              </label>
            );
          })}
        </div>
      </fieldset>

      {localError && (
        <p role="alert" className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-600">
          {localError}
        </p>
      )}

      <button
        type="submit"
        disabled={busy}
        className="w-full rounded-lg bg-blue-600 px-6 py-3 text-base font-semibold text-white shadow-sm transition hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-400"
      >
        {busy ? "Generating presentation…" : "Generate presentation"}
      </button>
    </form>
  );
}
