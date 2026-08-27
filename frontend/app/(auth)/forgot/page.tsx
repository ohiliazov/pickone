"use client";

import { useState, type FormEvent } from "react";
import { apiFetch } from "@/lib/api";

export default function ForgotPage() {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await apiFetch("/api/auth/password-reset/request", {
        method: "POST",
        body: { email },
      });
    } finally {
      setSubmitting(false);
      setDone(true);
    }
  }

  if (done) {
    return (
      <main className="mx-auto max-w-sm px-4 py-24 text-center">
        <p className="text-xl">Check your inbox.</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-sm px-4 py-16">
      <h1 className="text-2xl font-bold tracking-tight">Reset your password</h1>
      <form onSubmit={handleSubmit} className="mt-8 flex flex-col gap-4">
        <input
          type="email"
          required
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="rounded-md border border-[var(--po-border-strong)] bg-[var(--po-surface)] px-3 py-2"
        />
        <button
          type="submit"
          disabled={submitting}
          className="rounded-full bg-[var(--po-accent)] px-4 py-2 font-medium text-[var(--po-accent-ink)] disabled:opacity-50"
        >
          Send a link
        </button>
      </form>
    </main>
  );
}
