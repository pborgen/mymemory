import type { Metadata, Viewport } from "next";
import { Space_Grotesk, Syne } from "next/font/google";

import { Providers } from "@/providers";
import "./globals.css";

const sans = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const display = Syne({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});

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
  themeColor: "#e8eef4",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${sans.variable} ${display.variable}`}>
      <head>
        {/* Apply the saved theme before first paint to avoid a flash. */}
        <script
          dangerouslySetInnerHTML={{
            __html:
              `try{var t=localStorage.getItem("mymemory_theme");` +
              `if(t==="mint"||t==="sticker")t="lumen";` +
              `if(t&&t!=="lumen")document.documentElement.dataset.theme=t}catch(e){}`,
          }}
        />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
