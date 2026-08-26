/**
 * M0 scaffolding only. Every one of these is replaced by a real screen in
 * M5 (the loop) or M6 (the public pages). If one survives past M6, something
 * was missed.
 */
export function Placeholder({
  title,
  milestone,
  children,
}: {
  title: string;
  milestone: string;
  children?: React.ReactNode;
}) {
  return (
    <main className="mx-auto max-w-[var(--po-measure)] px-4 py-16">
      <h1 className="text-3xl font-bold tracking-tight">{title}</h1>
      {children}
      <p className="mt-8 text-sm text-[var(--po-ink-faint)]">
        Scaffolding. This screen arrives in {milestone}.
      </p>
    </main>
  );
}
