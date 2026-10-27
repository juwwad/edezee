/**
 * Shared types and the API client for the Edezee backend.
 *
 * The client mirrors the backend contracts in `backend/app/models.py`. Keeping
 * them hand-written (rather than generated) keeps the handoff simple: a
 * non-developer can read one small file to see every field the app uses.
 */

export type Depth = "High-Level" | "In-Depth";

export type Grounding = "research" | "model-knowledge" | "placeholder";

export interface Slide {
  topic: string;
  slide_number: number;
  slide_title: string;
  bullet_points: string[];
  speaker_notes: string;
  grounding: Grounding;
  sources: string[];
  attempts: number;
  degraded: boolean;
  error: string | null;
}

export interface Diagnostics {
  request_id: string;
  topic_count: number;
  slides_generated: number;
  degraded_slides: number;
  failed_topics: string[];
  total_latency_ms: number;
  per_topic_latency_ms: Record<string, number>;
  llm_calls: number;
  research_calls: number;
  research_used: boolean;
  model: string;
  depth: Depth;
  warnings: string[];
}

export interface GeneratePlanResponse {
  deck_title: string;
  slides: Slide[];
  diagnostics: Diagnostics;
}

export interface HealthResponse {
  status: "ok";
  llm_configured: boolean;
  research_configured: boolean;
  model: string;
}

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
    this.name = "ApiError";
  }
}

/** Read the backend's plain-language error body, falling back to a generic message. */
async function readError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string" && body.detail.trim()) {
      return body.detail;
    }
    if (Array.isArray(body.detail) && body.detail.length > 0) {
      const first = body.detail[0] as { msg?: string };
      if (first?.msg) {
        return first.msg;
      }
    }
  } catch {
    // Non-JSON error body; fall through to the generic message.
  }
  return `The server rejected the request (HTTP ${response.status}). Please try again.`;
}

export async function checkHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/health`, { signal });
  if (!response.ok) {
    throw new ApiError(await readError(response), response.status);
  }
  return (await response.json()) as HealthResponse;
}

export interface ProgressEvent {
  type: "progress";
  stage: string;
  message: string;
  completed: number;
  total: number;
}

export interface DoneEvent {
  type: "done";
  filename: string;
  slides: number;
  diagnostics: Diagnostics;
  slide_plan: Slide[];
  deck_base64: string;
}

export interface ErrorEvent {
  type: "error";
  message: string;
}

export type StreamEvent = ProgressEvent | DoneEvent | ErrorEvent;

export interface StreamOptions {
  syllabusText: string;
  depth: Depth;
  deckTitle: string;
  onProgress: (event: ProgressEvent) => void;
  signal?: AbortSignal;
}

export interface GenerateResult {
  blob: Blob;
  filename: string;
  slides: Slide[];
  diagnostics: Diagnostics;
}

/**
 * Stream a generation run using Server-Sent Events.
 *
 * Progress is reported through `onProgress`; the resolved value carries the
 * finished deck plus the diagnostics the UI shows in the run report.
 */
export async function generateDeckStream(options: StreamOptions): Promise<GenerateResult> {
  const { syllabusText, depth, deckTitle, onProgress, signal } = options;

  const response = await fetch(`${API_BASE_URL}/api/v1/generate/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      syllabus_text: syllabusText,
      depth,
      deck_title: deckTitle,
    }),
    signal,
  });

  if (!response.ok) {
    throw new ApiError(await readError(response), response.status);
  }
  if (!response.body) {
    throw new ApiError("The server returned an empty response stream.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: GenerateResult | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const rawEvent = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf("\n\n");

      const dataLine = rawEvent
        .split("\n")
        .find((line) => line.startsWith("data: "));
      if (!dataLine) {
        continue;
      }

      let event: StreamEvent;
      try {
        event = JSON.parse(dataLine.slice(6)) as StreamEvent;
      } catch {
        continue;
      }

      if (event.type === "progress") {
        onProgress(event);
      } else if (event.type === "error") {
        throw new ApiError(event.message);
      } else if (event.type === "done") {
        result = {
          blob: base64ToBlob(event.deck_base64),
          filename: event.filename,
          slides: event.slide_plan,
          diagnostics: event.diagnostics,
        };
      }
    }
  }

  if (!result) {
    throw new ApiError("The generation finished without producing a file. Please try again.");
  }
  return result;
}

function base64ToBlob(encoded: string): Blob {
  const binary = atob(encoded);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return new Blob([bytes as unknown as BlobPart], {
    type: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  });
}

/** Trigger a browser download for a generated deck. */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
