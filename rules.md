# Edezee - Rules & Contribution Guidelines

## 1. AI Collaboration Constraints (For OpenHands)
As an autonomous AI agent working on the Edezee project, you must adhere strictly to the following constraints to ensure a successful 5-day sprint delivery:
- **Scope Discipline:** Only build what is explicitly defined in `Project_Requirements.md` and `Architecture.md`. Do not add unrequested features (e.g., user authentication, complex styling options) that expand the v1 scope.
- **Secret Management:** NEVER hardcode API keys, secrets, or tokens in the codebase. Always use environment variables (`.env` files) and ensure they are added to `.gitignore`. Provide a `.env.example` file for user handoff.
- **Incremental Changes:** Implement changes sequentially. Verify that the core logic works before layering on UI polish or complex error handling.
- **No Silent Failures:** If a tool, API call, or dependency fails, fail loudly and surface a readable error message to the frontend. Do not swallow exceptions.

## 2. Coding Standards
- **Backend (Python/FastAPI):**
  - Use Python 3.10+.
  - Enforce strict type hinting (`def get_slides(topic: str) -> dict:`).
  - Use Pydantic models for all input/output validation.
  - Follow PEP 8 formatting standards.
- **Frontend (Next.js/React):**
  - Use TypeScript for all components and utilities.
  - Strictly use Tailwind CSS for styling (no custom CSS files or inline styles unless absolutely necessary for dynamic calculations).
  - Utilize Next.js App Router conventions.
  - Extract reusable UI elements into the `/components` directory.

## 3. Definition of Done (DoD)
A feature or phase is only considered "Done" when it meets all of the following criteria:
1. **End-to-End Functionality:** The code executes the required behavior successfully from the initial trigger to the final output.
2. **Error Handling:** Negative paths and edge cases (e.g., token overflow, empty inputs, API timeouts) are caught and handled gracefully with user-friendly UI messages.
3. **Type Safety:** No TypeScript `any` types are used where interfaces can be defined. Python code passes standard Pyright/mypy checks.
4. **Clean Configuration:** All secrets are externalized.
5. **No Regression:** New code does not break previously established happy paths.
6. **UI Responsiveness:** Frontend elements correctly reflect loading, success, and error states so the user is never left guessing.

## 4. Git and Commit Conventions
- Use semantic commit messages to keep the history readable for the final sprint handoff:
  - `feat:` for new features (e.g., `feat: integrate OpenRouter API for topic chunking`).
  - `fix:` for bug fixes (e.g., `fix: resolve timeout issue on large syllabus input`).
  - `refactor:` for code restructuring.
  - `docs:` for documentation updates.
  - `chore:` for dependency updates or configuration changes.