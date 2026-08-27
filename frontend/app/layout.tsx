import type { Metadata } from "next";
import { AuthProvider } from "@/components/AuthProvider";
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
        <AuthProvider>
          <Nav />
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}
