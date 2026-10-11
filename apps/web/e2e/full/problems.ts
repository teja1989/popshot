import type { Page } from "@playwright/test";

/**
 * Collects console errors, uncaught exceptions, failed responses and CSP violations from
 * here on. Call it after signIn (whose setup page isn't part of the app).
 */
export async function watchProblems(page: Page): Promise<string[]> {
  const problems: string[] = [];
  await page.addInitScript(() => {
    document.addEventListener("securitypolicyviolation", (event) => {
      console.error(`CSP violation: ${event.violatedDirective} ${event.blockedURI}`);
    });
  });
  page.on("console", (message) => {
    if (message.type() === "error") {
      problems.push(message.text());
    }
  });
  page.on("pageerror", (error) => problems.push(error.message));
  page.on("response", (response) => {
    if (response.status() >= 400) {
      problems.push(`${String(response.status())} ${response.url()}`);
    }
  });
  return problems;
}
