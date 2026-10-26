# Edezee - Architecture

## 1. System Overview
Edezee operates on a decoupled architecture, separating the client-side user interface from the heavy processing pipeline required for LLM inference and document generation. The system relies on Next.js for a responsive frontend and FastAPI for a Python-based backend that natively handles presentation assembly and AI orchestration.

## 2. Technology Stack
- **Frontend:** Next.js (App Router), React, Tailwind CSS.
- **Backend:** FastAPI (Python), Uvicorn.
- **AI / LLM Orchestration:** OpenRouter API (allowing access to models like Qwen or Claude for structured JSON generation).
- **Document Generation:** `python-pptx` (generates the binary `.pptx` file from structured data).
- **State/Storage:** Stateless architecture for v1. No database. Files are generated in-memory or in a temporary directory and streamed directly to the client.

## 3. End-to-End Data Flow
1. **Trigger:** The user pastes syllabus text and selects a depth level on the Next.js frontend, clicking "Generate Slides".
2. **API Call:** Next.js sends a POST request with the payload to the FastAPI endpoint (`/api/v1/generate`).
3. **Task 1: Parsing:** FastAPI processes the raw text, splitting it into a validated list of discrete topics.
4. **Task 2: Sequential Drafting (The LLM Pipeline):**
   - For *each* topic, FastAPI makes a synchronous or asynchronous call to OpenRouter.
   - The LLM is prompted with a strict system prompt to return structured JSON (Title, Bullet Points, Speaker Notes) for that specific topic.
   - *Crucial:* Processing one topic per LLM call prevents token truncation and generalization.
5. **Task 3: Slide Assembly:** The backend aggregates the JSON responses and feeds them into `python-pptx`, applying a pre-defined master slide template.
6. **Output:** FastAPI returns the generated `.pptx` file via a `StreamingResponse`. Next.js prompts the user's browser to download the file.

## 4. Data Contracts (Schemas)

**Client -> Server Request Payload:**
```json
{
  "syllabus_text": "1. Introduction to Next.js\n2. Server-side rendering vs Client-side rendering",
  "depth": "High-Level" // or "In-Depth"
}
```

**OpenRouter -> Server Structured Output (Per Topic):**
```json
{
  "slide_title": "Introduction to Next.js",
  "bullet_points": [
    "A React framework for production-grade applications.",
    "Supports hybrid static and server rendering.",
    "Provides automated route pre-fetching."
  ],
  "speaker_notes": "Emphasize that Next.js removes the configuration overhead of standard React apps..."
}
```

## 5. Application Structure
```text
edezee-monorepo/
├── frontend/                 # Next.js Application
│   ├── app/                  # Next.js App Router (page.tsx, layout.tsx)
│   ├── components/           # UI Components (InputForm, LoadingState, ErrorBanner)
│   └── package.json
└── backend/                  # FastAPI Application
    ├── main.py               # API entry point & routes
    ├── services/
    │   ├── llm_service.py    # OpenRouter API integration & prompts
    │   └── pptx_service.py   # python-pptx generation logic
    ├── models/               # Pydantic schemas for data validation
    └── requirements.txt
```

## 6. Technical Trade-offs & Decisions
- **Why Python/FastAPI backend?** While Next.js has serverless functions, robust presentation generation is vastly superior in Python (`python-pptx`) compared to Node.js alternatives. FastAPI provides high performance and native Pydantic validation.
- **Why OpenRouter?** Provides flexibility to swap models (e.g., testing Llama 3 against Qwen or Claude 3.5 Sonnet) without rewriting API logic, optimizing for cost and JSON compliance.
- **Why sequential processing over batch processing?** Sending the entire syllabus to the LLM at once degrades factual density and risks exceeding output token limits. Iterating topic-by-topic ensures high-quality, specific slides, trading slightly higher latency for significantly better quality.