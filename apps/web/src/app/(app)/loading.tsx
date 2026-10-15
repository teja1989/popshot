// Shown the moment you tap a link to another page, inside the tab bar that stays put, while
// the page itself is on its way: a quiet outline of a title and a few cards. Screen readers
// hear "Loading" once; the shapes are decoration.
export default function Loading() {
  return (
    <main
      aria-busy="true"
      data-page-loading=""
      className="mx-auto flex w-full max-w-md flex-col gap-6 px-5 pt-6 pb-12 lg:max-w-2xl lg:px-8 lg:pt-10"
    >
      <p className="sr-only" role="status">
        Loading
      </p>
      <div aria-hidden="true" className="flex flex-col gap-6 motion-safe:animate-pulse">
        <div className="h-9 w-2/3 rounded-xl bg-surface-high" />
        <div className="h-28 rounded-2xl bg-surface-high" />
        <div className="h-20 rounded-2xl bg-surface-high" />
        <div className="h-20 rounded-2xl bg-surface-high" />
      </div>
    </main>
  );
}
