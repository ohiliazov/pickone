import type { Metadata } from "next";
import { Placeholder } from "@/components/Placeholder";

export const metadata: Metadata = {
  title: "Add one",
  robots: { index: false, follow: false },
};

/** [SPEC §4.5] "What should we add?" — one input, 2–64 characters. M2. */
export default function AddPage() {
  return (
    <Placeholder title="What should we add?" milestone="M2">
      <p className="mt-4 text-[var(--po-ink-muted)]">
        Anything at all, up to 64 characters.
      </p>
    </Placeholder>
  );
}
