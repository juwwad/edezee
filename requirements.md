# Edezee - Project Requirements

## 1. Product Overview
Edezee is a dedicated, single-purpose application designed to eliminate the manual bottleneck of converting a raw educational syllabus into a structured, ready-to-teach slide deck. It prevents LLM generalization and token-limit truncation by processing syllabus topics sequentially through a controlled research and drafting pipeline.

## 2. Target User
- **Primary Persona:** Non-developer educators and teachers.
- **Key Pain Point:** Spending hours researching specific definitions for syllabus topics and formatting them into presentation software.
- **UX Expectation:** A streamlined, click-to-generate interface with zero requirement for presentation design skills.

## 3. Core Features (v1 - 5-Day Sprint Scope)
- **Syllabus Input Interface:** A simple text area where users paste syllabus topics line-by-line.
- **Depth Configuration:** A toggle to select the required depth of the slides (e.g., High-Level Overview vs. In-Depth Technical Definitions).
- **Sequential Processing Engine:** The system parses the syllabus into discrete topics, researching and drafting content for one topic at a time to maintain high factual density.
- **Presentation Compiler:** Programmatic assembly of the researched content into standardized slide layouts (Title, Content Bullet Points, Speaker Notes).
- **Direct Export:** A single-click download of a `.pptx` file.

## 4. Error Handling & Validation
- **Input Validation:** Reject empty inputs or formats that cannot be parsed into a list of topics.
- **Timeout Management:** Provide live loading states (e.g., "Researching topic 2 of 5...") to prevent user abandonment during the generation pipeline.
- **Graceful Fallbacks:** If a specific topic fails the research phase, the slide is generated with a placeholder and an error log is returned to the user interface.

## 5. Explicit Non-Goals
- Edezee is not a general-purpose AI chatbot.
- No complex user authentication, user accounts, or cloud storage of past presentations for v1.
- No heavy UI customization options (fonts, colors, layouts) for the presentation output; Edezee relies on a single, clean master template to guarantee formatting stability.