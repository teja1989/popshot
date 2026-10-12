"use client";

import { ErrorScreen } from "@/components/error-screen";

import "./globals.css";

// The root layout itself failed, so this brings its own html and body.
export default function AppError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <html lang="en">
      <body>
        <ErrorScreen error={error} source="app" reset={reset} />
      </body>
    </html>
  );
}
