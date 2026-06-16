import type { Metadata, Viewport } from "next";

import { Providers } from "@/providers";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000",
  ),
  title: "MyMemory — Tell it once. Ask it anytime.",
  description:
    "A private memory store for your life. Tell a chatbot anything you want to remember — a license plate, a Wi-Fi password, a friend's address — then just ask for it later. Powered by vector RAG.",
  icons: { icon: "/icon.svg" },
  openGraph: {
    title: "MyMemory — Tell it once. Ask it anytime.",
    description:
      "Your own private memory. Say it once, recall it forever. Powered by vector search.",
    type: "website",
    images: ["/logo.svg"],
  },
};

export const viewport: Viewport = {
  themeColor: "#14110f",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
