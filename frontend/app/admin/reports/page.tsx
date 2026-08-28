"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch, ApiError, type ReportedItemGroup, type ReportsResponse } from "@/lib/api";

export default function ReportsPage() {
  const [groups, setGroups] = useState<ReportedItemGroup[] | null>(null);
  const [notFound, setNotFound] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const data = await apiFetch<ReportsResponse>("/api/admin/reports");
      setGroups(data.reports);
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

  if (groups === null) {
    return <p className="p-8">Loading.</p>;
  }

  return (
    <main className="mx-auto max-w-3xl p-8">
      <h1 className="text-lg font-semibold">Reports</h1>
      <ul className="mt-6 flex flex-col gap-4">
        {groups.map((group) => (
          <li key={group.item.id} className="rounded-md border border-[var(--po-border)] p-4">
            <p className="font-medium">{group.item.text}</p>
            <p className="mt-1 text-sm text-[var(--po-ink-muted)]">
              {group.item.status} · {group.reports.length} report
              {group.reports.length === 1 ? "" : "s"}
            </p>
            <ul className="mt-2 flex flex-col gap-1 text-xs text-[var(--po-ink-muted)]">
              {group.reports.map((report) => (
                <li key={report.id}>
                  {report.reason} · {new Date(report.created_at).toLocaleString()}
                </li>
              ))}
            </ul>
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                onClick={() => void decide(group.item.id, "APPROVED")}
                className="rounded-full border border-[var(--po-border-strong)] px-3 py-1 text-sm hover:border-[var(--po-accent)]"
              >
                Approve
              </button>
              <button
                type="button"
                onClick={() => void decide(group.item.id, "REJECTED")}
                className="rounded-full border border-[var(--po-border-strong)] px-3 py-1 text-sm hover:border-[var(--po-accent)]"
              >
                Reject
              </button>
            </div>
          </li>
        ))}
        {groups.length === 0 && <p className="text-[var(--po-ink-muted)]">Empty.</p>}
      </ul>
    </main>
  );
}
