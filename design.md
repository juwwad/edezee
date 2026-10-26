# Edezee - Design Language and Tokens

## 1. Design Philosophy
Edezee follows a hyper-minimalist, utilitarian design system. Because the primary users are educators looking to save time, the interface must feel like a focused, single-purpose tool rather than a complex SaaS platform. The UI must aggressively reduce cognitive load and provide clear, continuous feedback during the long-running generation process.

## 2. Tailwind CSS Tokens & Color Palette
The color palette is built on trustworthiness and academic clarity, utilizing Tailwind's default color system.

- **Background:** `bg-slate-50` (Clean, low-contrast canvas)
- **Surface/Cards:** `bg-white` with `shadow-sm rounded-xl border border-slate-200`
- **Primary Text:** `text-slate-900` (Headings)
- **Secondary Text:** `text-slate-500` (Labels, helper text, placeholders)
- **Primary Action (Brand):** `bg-blue-600` hover:`bg-blue-700` text:`text-white`
- **Success/Completion:** `text-emerald-700` and `bg-emerald-50`
- **Error/Destructive:** `text-red-600` and `bg-red-50`
- **Focus Rings:** `focus:ring-2 focus:ring-blue-500 focus:outline-none focus:border-blue-500`

## 3. Typography
- **Font Family:** `font-sans` (Inter or system UI defaults like San Francisco/Segoe UI).
- **Headings:** Bold (`font-bold`), tight tracking (`tracking-tight`).
- **Body:** Standard weight, relaxed line height (`leading-relaxed`) for readability.

## 4. Core UI Components

### A. The Input Interface (Hero Section)
- **Container:** Centered max-width column (`max-w-2xl mx-auto mt-12`).
- **Textarea:** Prominent, minimum 10 rows tall. Must have clear placeholder text showing the expected syllabus format (e.g., "1. What is Next.js?\n2. Client vs. Server Components").
- **Depth Selector:** Simple radio group or segmented control (e.g., "High-Level Overview" vs. "Deep Technical Dive").
- **Primary Button:** Full width (`w-full`), large padding (`py-3`), bold text ("Generate Presentation"). 

### B. Loading & Status States
Since sequential LLM calls take time, the UI *must* keep the user informed to prevent abandonment.
- **Progress Indicator:** A dynamic status text element displaying the current pipeline state:
  - *Phase 1:* "Parsing syllabus topics..."
  - *Phase 2:* "Drafting slide 2 of 5: [Topic Name]..."
  - *Phase 3:* "Compiling PowerPoint presentation..."
- **Form Lock:** Disabled states on the textarea and button during generation to prevent duplicate submissions.

### C. Error States
- **Toast/Banner:** A red banner at the top of the container explaining the error in plain English without developer jargon (e.g., "We couldn't process this syllabus. Please check the formatting and try again.").

## 5. Slide Output Design (`python-pptx` template)
The generated `.pptx` file must adhere to strict accessibility and presentation standards to ensure it is immediately usable in a classroom setting:
- **Aspect Ratio:** 16:9 widescreen.
- **Background:** Solid white.
- **Typography:** Arial or Calibri to guarantee cross-platform rendering.
- **Title Slide:** Center-aligned, Title Size: 44pt bold, Subtitle Size: 28pt.
- **Content Slides:** 
  - Title: Top-aligned, 36pt.
  - Body (Bullet Points): Left-aligned, 24pt minimum size for readability in large lecture halls.
  - Constraint: Maximum of 5 bullet points per slide to prevent overcrowding.
- **Speaker Notes:** Cleanly injected into the notes pane for the teacher's reference.