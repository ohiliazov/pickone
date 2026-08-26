import type { Metadata } from "next";
import { Nav } from "@/components/Nav";
import { config, isIndexable } from "@/lib/config";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(config.baseUrl),
  title: {
    default: "PickOne — what would you choose?",
    template: "%s | PickOne",
  },
  description:
    "Two random things. Pick one. Your choice joins the world's ranking of everything.",
  // [SPEC §14.8] Only production may be indexed. A preview deploy that gets
  // indexed is the classic own-goal, so the default is the safe one.
  robots: isIndexable
    ? { index: true, follow: true }
    : { index: false, follow: false },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <Nav />
        {children}
      </body>
    </html>
  );
}
