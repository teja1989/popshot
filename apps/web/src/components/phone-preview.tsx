// A phone showing what Popshot looks like once a crew has games, for the landing page.
// Example data, labelled as such. Built from the app's own tokens so it matches the theme.

const STREAK = ["W", "L", "W", "W", "W"] as const;

const BOARD = [
  { name: "Riley", value: "4.62", width: "w-[92%]" },
  { name: "Casey", value: "4.18", width: "w-[76%]" },
  { name: "You", value: "3.97", width: "w-[71%]", you: true },
];

export function PhonePreview({ className = "" }: { className?: string }) {
  return (
    <div className={`relative mx-auto w-[280px] animate-rise [animation-delay:250ms] sm:w-[300px] ${className}`}>
      <div className="rounded-[46px] bg-[#06101a] p-2.5 shadow-[0_30px_80px_-20px_rgb(0_0_0/0.55)] lg:rotate-[2.5deg]">
        <div className="relative flex h-[560px] flex-col gap-3 overflow-hidden rounded-[38px] bg-bg px-4 pt-9 pb-4 text-ink sm:h-[600px]">
          <span className="absolute top-3 left-1/2 h-5 w-20 -translate-x-1/2 rounded-full bg-[#06101a]" />
          <div className="flex items-center justify-between">
            <span className="text-[17px] font-extrabold [font-stretch:110%]">Tuesday Dinkers</span>
            <span className="rounded-full bg-chip px-2 py-0.5 text-[10px] font-bold text-muted">Example</span>
          </div>

          <div className="flex flex-col gap-2 rounded-2xl border border-line bg-surface p-3">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-[10px] font-bold tracking-[0.1em] text-muted uppercase">Your form</p>
                <p className="text-[14px] font-bold">3-game win streak</p>
              </div>
              <div className="text-right">
                <p className="text-[30px] leading-none font-extrabold [font-stretch:75%]">3.97</p>
                <p className="text-[11px] font-bold text-win">▲ 0.14 this week</p>
              </div>
            </div>
            <div className="flex gap-1">
              {STREAK.map((r, i) => (
                <span
                  key={`${r}-${String(i)}`}
                  className={
                    r === "W"
                      ? "flex size-7 items-center justify-center rounded-md bg-win text-[11px] font-extrabold text-on-win"
                      : "flex size-7 items-center justify-center rounded-md border border-dashed border-loss text-[11px] font-extrabold text-muted"
                  }
                >
                  {r}
                </span>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-2 rounded-2xl border border-line bg-surface p-3">
            <p className="text-[10px] font-bold tracking-[0.1em] text-muted uppercase">Latest game</p>
            <div className="flex items-center justify-between text-[12px] font-semibold">
              <span>Casey &amp; Sam</span>
              <span className="text-[22px] font-extrabold [font-stretch:75%]">11 – 8</span>
              <span>You &amp; Alex</span>
            </div>
            <p className="text-[11px] text-muted">Logged by Casey · 2 min ago</p>
          </div>

          <div className="flex flex-col gap-2 rounded-2xl border border-line bg-surface p-3">
            <p className="text-[10px] font-bold tracking-[0.1em] text-muted uppercase">Crew points</p>
            {BOARD.map((row, i) => (
              <div key={row.name} className="flex items-center gap-2">
                <span className="w-3 text-[13px] font-extrabold text-muted [font-stretch:72%]">{i + 1}</span>
                <span className={`w-12 text-[12px] font-bold ${row.you ? "text-primary" : ""}`}>{row.name}</span>
                <span className="h-1.5 grow overflow-hidden rounded-full bg-chip">
                  <span className={`block h-full origin-left animate-grow-x rounded-full ${i === 0 ? "bg-win" : "bg-primary"} ${row.width}`} />
                </span>
                <span className="w-8 text-right text-[14px] font-extrabold [font-stretch:75%]">{row.value}</span>
              </div>
            ))}
          </div>

          <div className="grow" />
          <span className="flex h-11 items-center justify-center rounded-xl bg-ball text-[14px] font-extrabold text-on-ball">
            + Log a game
          </span>
        </div>
      </div>
    </div>
  );
}
