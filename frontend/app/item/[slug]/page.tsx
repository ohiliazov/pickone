import { Placeholder } from "@/components/Placeholder";

type Params = Promise<{ slug: string }>;

/** [SPEC §14.4] Indexable once the item has enough battles; noindex,follow below. */
export default async function ItemPage({ params }: { params: Params }) {
  const { slug } = await params;
  return <Placeholder title={slug} milestone="M6" />;
}
