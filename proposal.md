# Project Proposal: Syllabus-to-Slides Generator (Edezee)

## 1. Executive Summary
This project outlines the 5-day development sprint for an "Edezee" designed to automate the conversion of course syllabi into well-researched, structured presentation slides. This system solves a major operational bottleneck for educators by replacing hours of manual research, summarization, and PowerPoint formatting with an automated, multi-agent AI workflow. 

To prevent LLM generalization and token limit truncation, the system utilizes a chunked pipeline: it processes the syllabus topic-by-topic, retrieves specialized definitions via a Search API, structures the content into JSON, and programmatically generates the final presentation file.

## 2. 5-Day Sprint Timeline

### Day 1: Discover, Map, and Baseline
**Goal:** Define the exact bottleneck, establish baselines, and prepare test cases.
*   **Target User:** Educators and instructional designers.
*   **Workflow Map:** 
    *   *Trigger:* User receives a syllabus (topics/weeks).
    *   *Input:* Paste syllabus text into UI; select target audience/depth.
    *   *Tool/Judgment:* AI chunks topics, researches each via Search API, and formats to JSON.
    *   *Output:* Downloadable presentation file (e.g., `.pptx`).
*   **Baseline Metrics:** Measure time taken to manually research and create a 10-slide deck from 3 syllabus topics (vs. standard ChatGPT prompting).
*   **Deliverable:** 8–12 documented test cases (happy path, niche topics, vague topics, slide overflow scenarios). 

### Day 2: Design the System and Ship v0
**Goal:** Translate workflow into architecture and make the first happy path work programmatically.
*   **Architecture & Flow:** Define the boundaries between the frontend interface, the backend API, the Research Agent, the Drafting Agent, and the Generation Engine.
*   **Tooling Choices:** 
    *   *LLM:* Function-calling capable model for structured JSON outputs.
    *   *Integrations:* Search API (e.g., Tavily) for research; Slide Generator (e.g., `python-pptx` or Marp) for file creation.
*   **Deliverable:** A `v0` script (backend only) that takes one hardcoded syllabus topic, researches it, structures it, and outputs a basic slide file.

### Day 3: Build the Working Core
**Goal:** Complete the end-to-end flow for a non-developer user.
*   **User Interface:** Build a simple, accessible web UI (e.g., Next.js/React form) for inputting topics and downloading the result.
*   **Integration:** Connect the UI to the backend pipeline. Ensure the two real data integrations (Search API and Slide Generation) are fully linked.
*   **State & Validation:** Implement structured output enforcement for slide chunking. Separate secrets/API keys from the codebase.
*   **Deliverable:** First successful end-to-end execution by a proxy user through the UI.

### Day 4: Evaluate, Break, and Harden
**Goal:** Stress-test the system, handle failures, and analyze reliability.
*   **Testing:** Run the 8-12 test cases established on Day 1. 
*   **Failure Handling:** Deliberately test token overflow, bad search results, and invalid JSON responses. Implement retries, fallbacks (e.g., LLM internal knowledge if search fails), and useful UI error messages.
*   **Evaluation:** Compare Day 4 metrics (quality, latency, manual-touch reduction) against the Day 1 baseline.
*   **Deliverable:** Hardened codebase with logging, error boundaries, and root-cause analysis documentation for at least three failure cases.

### Day 5: Handoff, Prove Value, and Present
**Goal:** Package the project so anyone can run, trust, and improve it.
*   **Documentation:** Finalize the User README, Operator Runbook, and one-command setup guide. 
*   **Case Study:** Write the portfolio-ready case study detailing architecture, trade-offs, AI collaboration, and limitations.
*   **Media:** Record the required 5-minute screen-recorded demo showing the baseline, live flow, UX, and failure handling.
*   **Deliverable:** Final runnable repository and evaluation package ready for submission.

## 3. Project Documentation Context
For the complete context of this system, the AI agent must reference the following files:
*   **Project Requirements:** See `Project Requirements.md`
*   **Technical Architecture:** See `Architecture.md`
*   **Design Language:** See `Design.md`
*   **Contribution Rules:** See `rules.md`
*   **Build Phases:** See `Phases.md`
*   **Project State/Memory:** See `Memory.md`
*   **Website Overview:** See `website.md`