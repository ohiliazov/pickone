"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch, ApiError, type ModerationQueueItem, type ModerationQueueResponse } from "@/lib/api";

export default function ModerationQueuePage() {
  const [items, setItems] = useState<ModerationQueueItem[] | null>(null);
  const [notFound, setNotFound] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const data = await apiFetch<ModerationQueueResponse>("/api/admin/moderation/queue");
      setItems(data.items);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 404 || err.status === 401)) {
        setNotFound(true);
      }
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const decide = async (id: string, decision: "APPROVED" | "REJECTED") => {
    await apiFetch(`/api/admin/items/${id}/decision`, {
      method: "POST",
      body: { decision },
    });
    void refresh();
  };

  if (notFound) {
    return <p className="p-8">Not here.</p>;
  }

  if (items === null) {
    return <p className="p-8">Loading.</p>;
  }

  return (
    <main className="mx-auto max-w-3xl p-8">
      <h1 className="text-lg font-semibold">Moderation queue</h1>
      <ul className="mt-6 flex flex-col gap-4">
        {items.map((item) => (
          <li key={item.id} className="rounded-md border border-[var(--po-border)] p-4">
            <p className="font-medium">{item.text}</p>
            <p className="mt-1 text-sm text-[var(--po-ink-muted)]">
              {item.status} · {item.latest_provider ?? "no provider"} ·{" "}
              {new Date(item.created_at).toLocaleString()}
            </p>
            {Object.keys(item.latest_scores).length > 0 && (
              <p className="mt-1 text-xs text-[var(--po-ink-muted)]">
                {Object.entries(item.latest_scores)
                  .map(([k, v]) => `${k}: ${v.toFixed(3)}`)
                  .join(", ")}
              </p>
            )}
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                onClick={() => void decide(item.id, "APPROVED")}
                className="rounded-full border border-[var(--po-border-strong)] px-3 py-1 text-sm hover:border-[var(--po-accent)]"
              >
                Approve
              </button>
              <button
                type="button"
                onClick={() => void decide(item.id, "REJECTED")}
                className="rounded-full border border-[var(--po-border-strong)] px-3 py-1 text-sm hover:border-[var(--po-accent)]"
              >
                Reject
              </button>
            </div>
          </li>
        ))}
        {items.length === 0 && <p className="text-[var(--po-ink-muted)]">Empty.</p>}
      </ul>
    </main>
  );
}
