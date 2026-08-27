"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { useAuth } from "@/components/AuthProvider";
import { apiFetch, ApiError, setCsrfToken, type UserOut } from "@/lib/api";

type LoginResponse = {
  user: UserOut;
  csrf_token: string;
};

export default function LoginPage() {
  const router = useRouter();
  const { refresh } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const result = await apiFetch<LoginResponse>("/api/auth/login", {
        method: "POST",
        body: { email, password },
      });
      setCsrfToken(result.csrf_token);
      await refresh();
      router.push("/play");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto max-w-sm px-4 py-16">
      <h1 className="text-2xl font-bold tracking-tight">Log in</h1>
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
          Log in
        </button>
      </form>
      <div className="mt-6 flex justify-between text-sm text-[var(--po-ink-muted)]">
        <Link href="/register" className="underline">
          Make an account
        </Link>
        <Link href="/forgot" className="underline">
          Forgot it?
        </Link>
      </div>
    </main>
  );
}
