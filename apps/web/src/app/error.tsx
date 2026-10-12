"use client";

import { ErrorScreen } from "@/components/error-screen";

// A page that throws while rendering lands here, inside the root layout.
export default function PageError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <ErrorScreen error={error} source="page" reset={reset} />;
}
