import { Placeholder } from "@/components/Placeholder";

/**
 * [SPEC §10.4] Ratings render always signed — +487, −312, 0 — with a real
 * minus sign, because the sign is the thing the number is for.
 * [SPEC §10.5] Only ranked items (RD below threshold) appear here.
 */
export default function RankingsPage() {
  return (
    <Placeholder title="Rankings" milestone="M6">
      <p className="mt-4 text-[var(--po-ink-muted)]">
        Everything, ranked by everyone.
      </p>
    </Placeholder>
  );
}
