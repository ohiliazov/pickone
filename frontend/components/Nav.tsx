import Link from "next/link";

/**
 * The entire navigation. [SPEC §5.5]
 *
 * Five items. Do not add a hamburger for three links, and do not add a sixth
 * item without deleting one — the product has exactly one primary verb.
 */
export function Nav() {
  return (
    <header className="border-b border-[var(--po-border)]">
      <nav
        aria-label="Main"
        className="mx-auto flex max-w-5xl items-center gap-6 px-4 py-4"
      >
        <Link
          href="/"
          className="text-lg font-extrabold tracking-tight uppercase"
        >
          PickOne
        </Link>

        <div className="ml-auto flex items-center gap-5 text-sm">
          <Link href="/play" className="hover:text-[var(--po-accent)]">
            Pick One
          </Link>
          <Link href="/rankings" className="hover:text-[var(--po-accent)]">
            Rankings
          </Link>
          <Link
            href="/add"
            className="rounded-full border border-[var(--po-border-strong)] px-3 py-1.5 font-medium hover:border-[var(--po-accent)] hover:text-[var(--po-accent)]"
          >
            + Add one
          </Link>
          <Link href="/login" className="text-[var(--po-ink-muted)] hover:text-[var(--po-ink)]">
            Log in
          </Link>
        </div>
      </nav>
    </header>
  );
}
