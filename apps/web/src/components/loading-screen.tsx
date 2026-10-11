import { Brand } from "./ui/brand";

export function LoadingScreen() {
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col px-7 pt-14 pb-9">
      <Brand />
      <p className="mt-11 text-muted">One moment…</p>
    </main>
  );
}
