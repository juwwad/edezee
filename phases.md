# Edezee - Build Phases

This document outlines the sequential development phases for the Edezee AI OS Mini. OpenHands must complete these phases in order, verifying the Definition of Done (from `rules.md`) at each step.

## Phase 1: Environment Setup & Scaffolding (Day 1-2)
**Goal:** Establish the monorepo structure and install required dependencies.
- Initialize a Next.js (App Router) project in the `/frontend` directory with Tailwind CSS and TypeScript.
- Initialize a Python virtual environment in the `/backend` directory.
- Install FastAPI, Uvicorn, and Pydantic in the backend.
- Install `python-pptx` and the `openai` (or `requests`) library for OpenRouter integration.
- Create boilerplate `.env.example` files for both frontend and backend.

## Phase 2: Backend Core - LLM Pipeline (Day 2)
**Goal:** Build the engine that converts a single syllabus topic into structured JSON.
- Define Pydantic models for incoming requests (Syllabus text) and LLM structured outputs (Title, Bullets, Speaker Notes).
- Create the `/api/v1/generate` FastAPI endpoint.
- Implement the OpenRouter API call with a strict system prompt enforcing the JSON schema.
- **Test:** Verify the API can take a single hardcoded string and return valid JSON.

## Phase 3: Backend Core - PPTX Compiler (Day 2-3)
**Goal:** Convert the structured JSON into a downloadable presentation.
- Implement the `python-pptx` service to generate a presentation in memory.
- Create a master slide template function (Title slide + Content slides).
- Loop through the JSON responses from Phase 2 and map them to slide layouts.
- Update the FastAPI endpoint to return a `StreamingResponse` with the `application/vnd.openxmlformats-officedocument.presentationml.presentation` MIME type.
- **Test:** Hit the API endpoint via Postman/cURL and successfully download/open the `.pptx` file.

## Phase 4: Frontend Core - UI Integration (Day 3)
**Goal:** Build the user interface and connect it to the backend.
- Build the main hero section with the Textarea for syllabus input and the Depth Selector.
- Implement the form submission logic to send a POST request to the FastAPI backend.
- Add file download handling in the browser to save the returned `.pptx` blob.
- **Test:** End-to-end execution of a 3-topic syllabus via the UI.

## Phase 5: State Management & Hardening (Day 3-4)
**Goal:** Improve UX and handle long-running pipeline states.
- Implement dynamic loading states in the frontend (e.g., "Parsing topics...", "Drafting slides...").
- Add error boundaries and toast notifications for API failures.
- Implement sequential processing in the backend (looping through topics one-by-one to avoid token limits).
- Add timeout handling and graceful fallbacks (e.g., if one topic fails, insert a placeholder slide instead of crashing the whole deck).

## Phase 6: Handoff & Documentation (Day 5)
**Goal:** Prepare the project for final submission.
- Write the `README.md` with a one-command setup guide (or clear 3-step guide for frontend + backend).
- Ensure all inline code comments explain the "why" behind the sequential AI generation pipeline.
- Clean up any temporary files or debug statements.