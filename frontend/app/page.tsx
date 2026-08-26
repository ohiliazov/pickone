import { Placeholder } from "@/components/Placeholder";

/**
 * [SPEC §14.2] The home page is both the game and a content page: cards above
 * the fold, real server-rendered content below (top 10, most-played
 * comparisons, newest items) so it is a genuine hub that passes crawl equity
 * to the leaves. M6 builds that; M5 makes the cards live.
 */
export default function HomePage() {
  return (
    <Placeholder title="What would you choose?" milestone="M5 + M6">
      <p className="mt-4 text-[var(--po-ink-muted)]">
        Two random things. Pick one.
      </p>
    </Placeholder>
  );
}
