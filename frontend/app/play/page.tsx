import type { Metadata } from "next";
import { Placeholder } from "@/components/Placeholder";

// [SPEC §14.4] /play has no indexable content and must never be crawled.
export const metadata: Metadata = {
  title: "Pick one",
  robots: { index: false, follow: false },
};

/** The screen that is the product. [SPEC §5.1] Built in M5, powered by M4. */
export default function PlayPage() {
  return <Placeholder title="Pick One" milestone="M5" />;
}
