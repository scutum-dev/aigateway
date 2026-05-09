import type { MetadataRoute } from "next";

/**
 * Auto-generated sitemap at /sitemap.xml.
 *
 * The chat product is a single-page app — there's only one indexable URL
 * (the homepage with the chat input + About section). The parent sitemap
 * at https://scutum.dev/sitemap.xml also lists this URL; this file exists
 * mainly so the robots.txt entry that advertises chat.scutum.dev/sitemap.xml
 * resolves rather than 404s. Crawlers prefer each origin to ship its own
 * sitemap, even when the content overlaps.
 *
 * Next.js builds this file into a static /sitemap.xml at compile time, so
 * the response is served without any runtime cost.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  const base =
    process.env.NEXT_PUBLIC_APP_URL || "https://chat.scutum.dev";

  return [
    {
      url: base,
      lastModified: new Date(),
      changeFrequency: "weekly",
      priority: 1.0,
    },
  ];
}
