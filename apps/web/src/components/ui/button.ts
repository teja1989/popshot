// Button looks for <button> and <Link>. Classes only, so it works in server components and
// never needs inline styles (which the CSP blocks).

export type ButtonVariant = "primary" | "action" | "quiet" | "danger";

const base =
  "inline-flex min-h-12 cursor-pointer items-center justify-center gap-2 rounded-xl px-5 " +
  "text-[17px] font-bold no-underline transition-transform duration-150 ease-court " +
  "hover:-translate-y-px active:translate-y-px " +
  "disabled:cursor-progress disabled:opacity-60 disabled:hover:translate-y-0";

const variants: Record<ButtonVariant, string> = {
  // The main way forward on a screen.
  primary: "bg-primary text-on-primary",
  // The one thing you came to do (log a game): the ball-yellow accent.
  action: "bg-ball text-on-ball",
  quiet: "border border-line bg-transparent text-ink",
  // Confirming something that can't be undone from the app.
  danger: "border-2 border-warn bg-transparent text-warn",
};

export function buttonClass(variant: ButtonVariant = "primary", extra = ""): string {
  return `${base} ${variants[variant]} ${extra}`.trim();
}
