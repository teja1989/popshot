// Light, dark, or follow the device. The choice lives in this browser only (localStorage)
// and is applied as data-theme on <html>, which globals.css already honours.

export type ThemeChoice = "system" | "light" | "dark";

export const THEME_KEY = "popshot.theme";

// Runs in <head> before first paint (with the page's CSP nonce), so a saved dark theme
// never flashes light. Kept tiny and free of anything user-controlled.
export const THEME_INIT_SCRIPT = `try{var t=localStorage.getItem("${THEME_KEY}");if(t==="light"||t==="dark"){document.documentElement.dataset.theme=t}}catch(e){}`;

export function readTheme(): ThemeChoice {
  try {
    const value = localStorage.getItem(THEME_KEY);
    return value === "light" || value === "dark" ? value : "system";
  } catch {
    return "system";
  }
}

export function applyTheme(choice: ThemeChoice): void {
  const root = document.documentElement;
  if (choice === "system") {
    delete root.dataset.theme;
  } else {
    root.dataset.theme = choice;
  }
  try {
    if (choice === "system") {
      localStorage.removeItem(THEME_KEY);
    } else {
      localStorage.setItem(THEME_KEY, choice);
    }
  } catch {
    // Private mode or blocked storage: the choice still applies until the page closes.
  }
}
