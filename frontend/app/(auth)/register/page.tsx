"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { useAuth } from "@/components/AuthProvider";
import { apiFetch, ApiError, setCsrfToken, type UserOut } from "@/lib/api";

type RegisterResponse = {
  user: UserOut;
  csrf_token: string;
  converted_from_guest: boolean;
  picks_kept: number;
};

export default function RegisterPage() {
  const router = useRouter();
  const { refresh } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const result = await apiFetch<RegisterResponse>("/api/auth/register", {
        method: "POST",
        body: { email, password },
      });
      setCsrfToken(result.csrf_token);
      await refresh();
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <main className="mx-auto max-w-sm px-4 py-24 text-center">
        <p className="text-xl">Check your inbox.</p>
        <button
          type="button"
          onClick={() => router.push("/play")}
          className="mt-6 text-sm text-[var(--po-ink-muted)] underline"
        >
          Continue
        </button>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-sm px-4 py-16">
      <h1 className="text-2xl font-bold tracking-tight">Make an account</h1>
      <form onSubmit={handleSubmit} className="mt-8 flex flex-col gap-4">
        <input
          type="email"
          required
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="rounded-md border border-[var(--po-border-strong)] bg-[var(--po-surface)] px-3 py-2"
        />
        <input
          type="password"
          required
          minLength={10}
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="rounded-md border border-[var(--po-border-strong)] bg-[var(--po-surface)] px-3 py-2"
        />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={submitting}
          className="rounded-full bg-[var(--po-accent)] px-4 py-2 font-medium text-[var(--po-accent-ink)] disabled:opacity-50"
        >
          Make an account
        </button>
      </form>
      <p className="mt-6 text-sm text-[var(--po-ink-muted)]">
        Already have one?{" "}
        <Link href="/login" className="underline">
          Log in
        </Link>
      </p>
    </main>
  );
}
