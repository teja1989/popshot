// Initials in a circle. Profile photos aren't loaded: the CSP allows them, but initials
// keep the roster calm and readable, and work for guests who have no photo.

export function initials(name: string | null | undefined): string {
  const trimmed = name?.trim() ?? "";
  if (!trimmed) {
    return "?";
  }
  const parts = trimmed.split(/\s+/);
  const first = parts[0] ?? "";
  const last = parts.length > 1 ? (parts[parts.length - 1] ?? "") : "";
  return (Array.from(first)[0] ?? "") + (Array.from(last)[0] ?? "") || "?";
}

export function Avatar({
  name,
  tone = "chip",
  size = "md",
}: {
  name: string | null | undefined;
  tone?: "chip" | "ball";
  size?: "md" | "lg";
}) {
  const tones = { chip: "bg-chip text-ink", ball: "bg-ball text-on-ball" };
  const sizes = { md: "size-10 text-[13px]", lg: "size-12 text-[15px]" };
  return (
    <span
      aria-hidden="true"
      className={`flex shrink-0 items-center justify-center rounded-full font-extrabold uppercase ${tones[tone]} ${sizes[size]}`}
    >
      {initials(name)}
    </span>
  );
}
