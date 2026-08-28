"use client";

import Link from "next/link";
import { useState } from "react";
import { useAuth } from "@/components/AuthProvider";

export function Nav() {
  const { user, loading, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const [slowerPace, setSlowerPace] = useState(false);

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

          {loading ? null : user && !user.is_guest ? (
            <div className="relative">
              <button
                type="button"
                onClick={() => setMenuOpen((v) => !v)}
                aria-haspopup="menu"
                aria-expanded={menuOpen}
                className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--po-accent)] text-sm font-semibold text-[var(--po-accent-ink)]"
              >
                {(user.email ?? "?").charAt(0).toUpperCase()}
              </button>
              {menuOpen && (
                <div
                  role="menu"
                  className="absolute right-0 z-10 mt-2 w-56 rounded-md border border-[var(--po-border)] bg-[var(--po-surface)] p-2 shadow-lg"
                >
                  <p className="truncate px-2 py-1 text-[var(--po-ink-muted)]">
                    {user.email}
                  </p>
                  <label className="flex items-center gap-2 rounded px-2 py-1.5 hover:bg-[var(--po-bg)]">
                    <input
                      type="checkbox"
                      checked={slowerPace}
                      onChange={(e) => setSlowerPace(e.target.checked)}
                    />
                    Slower pace
                  </label>
                  {user.is_admin && (
                    <Link
                      href="/admin/moderation"
                      role="menuitem"
                      onClick={() => setMenuOpen(false)}
                      className="block rounded px-2 py-1.5 hover:bg-[var(--po-bg)]"
                    >
                      Admin
                    </Link>
                  )}
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setMenuOpen(false);
                      void logout();
                    }}
                    className="w-full rounded px-2 py-1.5 text-left hover:bg-[var(--po-bg)]"
                  >
                    Log out
                  </button>
                </div>
              )}
            </div>
          ) : (
            <Link href="/login" className="text-[var(--po-ink-muted)] hover:text-[var(--po-ink)]">
              Log in
            </Link>
          )}
        </div>
      </nav>
    </header>
  );
}
