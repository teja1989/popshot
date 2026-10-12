"use client";

import { useEffect } from "react";

import { reportError } from "@/lib/report-error";

// Errors no screen caught: thrown in an event handler or timer, or a promise nobody
// handled. Reported quietly; the page carries on.

// Browser noise that isn't a Popshot bug.
const IGNORED = [/ResizeObserver loop/i, /^Script error\.?$/i];

export function ErrorReporter() {
  useEffect(() => {
    function onError(event: ErrorEvent) {
      const error: unknown = event.error ?? event.message;
      if (IGNORED.some((pattern) => pattern.test(event.message))) {
        return;
      }
      reportError(error, "window");
    }
    function onRejection(event: PromiseRejectionEvent) {
      reportError(event.reason, "promise");
    }
    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onRejection);
    return () => {
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onRejection);
    };
  }, []);
  return null;
}
