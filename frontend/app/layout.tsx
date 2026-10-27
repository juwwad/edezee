import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Edezee — Syllabus to slides in one click",
  description:
    "Paste a course syllabus and get a researched, ready-to-teach PowerPoint deck with speaker notes.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="bg-slate-50 font-sans text-slate-900 antialiased">
        {children}
      </body>
    </html>
  );
}
