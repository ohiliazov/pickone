"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { useAuth } from "@/components/AuthProvider";
import { apiFetch, ApiError, type ItemSummary } from "@/lib/api";

type CreateItemResponse = {
  item: ItemSummary;
  message: string;
};

const MAX_LENGTH = 64;
const COUNTER_THRESHOLD = 48;

export function AddForm() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [existingSlug, setExistingSlug] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && (!user || user.is_guest)) {
      router.replace("/register");
    }
  }, [loading, user, router]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setExistingSlug(null);
    setSubmitting(true);
    try {
      const result = await apiFetch<CreateItemResponse>("/api/items", {
        method: "POST",
        body: { text },
      });
      setMessage(result.message);
      if (result.item.status === "APPROVED") {
        setTimeout(() => {
          router.push(`/play?seed=${result.item.id}`);
        }, 800);
      }
    } catch (err) {
      if (err instanceof ApiError && err.code === "already_exists") {
        setExistingSlug((err.details.slug as string | undefined) ?? null);
        setError("Already here.");
      } else if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Something went wrong.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (message) {
    return (
      <main className="mx-auto max-w-sm px-4 py-24 text-center">
        <p className="text-xl">{message}</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-sm px-4 py-16">
      <h1 className="text-2xl font-bold tracking-tight">What should we add?</h1>
      <form onSubmit={handleSubmit} className="mt-8 flex flex-col gap-2">
        <input
          type="text"
          required
          minLength={2}
          maxLength={MAX_LENGTH}
          value={text}
          onChange={(e) => setText(e.target.value)}
          className="rounded-md border border-[var(--po-border-strong)] bg-[var(--po-surface)] px-3 py-2"
        />
        <div className="flex items-center justify-between text-xs text-[var(--po-ink-muted)]">
          {text.length >= COUNTER_THRESHOLD ? (
            <span>
              {text.length}/{MAX_LENGTH}
            </span>
          ) : (
            <span />
          )}
          <span title="That's why.">Why 64 characters?</span>
        </div>
        {error && (
          <p className="text-sm text-red-600">
            {error}{" "}
            {existingSlug && (
              <Link href={`/item/${existingSlug}`} className="underline">
                See it
              </Link>
            )}
          </p>
        )}
        <button
          type="submit"
          disabled={submitting}
          className="mt-2 rounded-full bg-[var(--po-accent)] px-4 py-2 font-medium text-[var(--po-accent-ink)] disabled:opacity-50"
        >
          Add one
        </button>
      </form>
    </main>
  );
}
