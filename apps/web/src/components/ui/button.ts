// Button looks for <button> and <Link>. Classes only, so it works in server components and
// never needs inline styles (which the CSP blocks).

export type ButtonVariant = "primary" | "action" | "quiet" | "danger";

const base =
  "inline-flex min-h-12 cursor-pointer items-center justify-center gap-2 rounded-full px-6 " +
  "text-lead font-bold no-underline transition-[scale,filter] duration-150 ease-standard " +
  "hover:brightness-95 active:scale-[0.97] " +
  "disabled:cursor-progress disabled:opacity-60 disabled:hover:brightness-100 disabled:active:scale-100";

const variants: Record<ButtonVariant, string> = {
  // The main way forward on a screen.
  primary: "bg-primary text-on-primary",
  // The one thing you came to do (log a game): the ball-yellow accent.
  action: "bg-ball text-on-ball",
  // Everything else: a soft tonal fill (Material 3's tonal button).
  quiet: "bg-secondary-container text-on-secondary-container",
  // Confirming something that can't be undone from the app.
  danger: "border-2 border-warn bg-transparent text-warn",
};

export function buttonClass(variant: ButtonVariant = "primary", extra = ""): string {
  return `${base} ${variants[variant]} ${extra}`.trim();
}
