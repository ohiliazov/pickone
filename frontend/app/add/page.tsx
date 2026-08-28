import type { Metadata } from "next";
import { AddForm } from "@/components/AddForm";

export const metadata: Metadata = {
  title: "Add one",
  robots: { index: false, follow: false },
};

export default function AddPage() {
  return <AddForm />;
}
