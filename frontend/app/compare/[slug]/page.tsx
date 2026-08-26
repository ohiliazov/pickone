import { Placeholder } from "@/components/Placeholder";

type Params = Promise<{ slug: string }>;

/**
 * [SPEC §14.3] Only comparisons that exist in the database are addressable.
 * A pair that has never battled is a 404, never a generated page — this one
 * rule is what stops n(n−1)/2 thin pages from reaching the index.
 */
export default async function ComparePage({ params }: { params: Params }) {
  const { slug } = await params;
  return <Placeholder title={slug.replace("-vs-", " vs ")} milestone="M6" />;
}
