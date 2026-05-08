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
  title: `${SITE} — AI search with interactive answers. Sources cited.`,
  description:
    "AI search where the answer is software, not text. Ask questions, get interactive charts, calculators, and tables. Sources cited. Free, no signup.",
  metadataBase: new URL(APP_URL),
  alternates: { canonical: APP_URL },
  openGraph: {
    type: "website",
    siteName: "Scutum",
    url: APP_URL,
    title: `${SITE} — AI search with interactive answers`,
    description: "Most AI search returns text. We return software.",
    images: ["/og-chat.jpg"],
  },
  twitter: {
    card: "summary_large_image",
    title: `${SITE} — AI search with interactive answers`,
    description: "Most AI search returns text. We return software.",
    images: ["/og-chat.jpg"],
  },
  robots: { index: true, follow: true },
};

// Schema.org SoftwareApplication markup so search engines and LLM crawlers
// can model the chat product as a discrete entity (separate from the parent
// Scutum org, which has its own Organization JSON-LD on scutum.dev). Inline
// JSON-LD via a <script> block in <head> rather than a metadata field —
// Next.js's Metadata API doesn't have a direct slot for arbitrary JSON-LD.
const softwareApplicationLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: SITE,
  applicationCategory: "AI Search",
  operatingSystem: "Web",
  url: APP_URL,
  description:
    "AI search where the answer is software, not text. Ask questions, get interactive charts, calculators, and tables. Sources cited. Free, no signup.",
  offers: {
    "@type": "Offer",
    price: "0",
    priceCurrency: "USD",
  },
  publisher: {
    "@type": "Organization",
    name: "Scutum",
    url: "https://scutum.dev",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${instrumentSerif.variable} ${jetbrainsMono.variable}`}
    >
      <head>
        <script
          type="application/ld+json"
          // dangerouslySetInnerHTML is the canonical way to ship a JSON-LD
          // block from a React component. We control the input fully (it's a
          // static object stringified at module scope) so there's no XSS surface.
          dangerouslySetInnerHTML={{
            __html: JSON.stringify(softwareApplicationLd),
          }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
