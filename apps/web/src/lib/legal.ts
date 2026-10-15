// Who runs Popshot, for the privacy policy, terms and contact page. Not secret, so it lives
// here. The bracketed values are placeholders: while any is left, the pages say they're a
// draft. Replace them (and the date) when the company details are final.

export const LEGAL = {
  company: "[Company name] LLC",
  state: "[State]",
  contactEmail: "hello@popshotpb.com",
  // When the current wording took effect.
  updated: "2026-10-12",
} as const;

export function isDraft(legal: { company: string; state: string; contactEmail: string } = LEGAL): boolean {
  return (
    [legal.company, legal.state].some((value) => /\[.*\]/.test(value)) ||
    /@example\.(com|org|net)$/.test(legal.contactEmail)
  );
}

export function updatedOn(iso: string = LEGAL.updated): string {
  return new Date(`${iso}T12:00:00Z`).toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}
