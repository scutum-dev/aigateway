import type { Metadata } from "next";
import { Inter, Instrument_Serif, JetBrains_Mono } from "next/font/google";
import "./globals.css";

// next/font self-hosts these from Google Fonts at build time (zero CLS,
// no third-party network roundtrip on first paint). The CSS variables
// match what globals.css references so the rest of the styling is
// untouched.
const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-sans",
  display: "swap",
});
const instrumentSerif = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
  variable: "--font-serif",
  display: "swap",
});
const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

// `||` (not `??`) so empty-string env vars also fall through to defaults —
// Vercel's `vercel pull` can return blank values for vars defined-but-unset,
// and `new URL("")` later in metadataBase throws `ERR_INVALID_URL` on build.
const SITE = process.env.NEXT_PUBLIC_SITE_NAME || "Scutum Research";
const APP_URL = process.env.NEXT_PUBLIC_APP_URL || "https://chat.scutum.dev";

export const metadata: Metadata = {
  title: `${SITE} — search with citations, routed through your AI control plane`,
  description:
    "Ask anything. Multi-model routing picks the best model for the task. " +
    "Every query is auditable, costs are transparent, models are pluggable.",
  metadataBase: new URL(APP_URL),
  openGraph: {
    title: SITE,
    description: "Self-hosted Perplexity for enterprise.",
    url: APP_URL,
    siteName: SITE,
    locale: "en_US",
    type: "website",
  },
  robots: { index: true, follow: true },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${instrumentSerif.variable} ${jetbrainsMono.variable}`}
    >
      <body>{children}</body>
    </html>
  );
}
