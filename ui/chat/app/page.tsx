import Chat from "@/components/Chat";

export default function Home() {
  return (
    <main className="min-h-screen flex flex-col">
      <header className="border-b border-[var(--color-border)] px-6 py-4">
        <a
          href="/"
          className="text-2xl italic font-normal"
          style={{ fontFamily: "var(--font-serif)" }}
        >
          Scutum Research
        </a>
        <span className="ml-3 text-xs text-[var(--color-text-subtle)] uppercase tracking-wider">
          beta
        </span>
      </header>
      <div className="flex-1 flex flex-col max-w-3xl w-full mx-auto px-4 py-8">
        <Chat />
      </div>

      {/*
        About section — renders below the chat, separated by 96px whitespace.
        Subtle text-tertiary styling so it doesn't compete with the active
        chat UI but is fully indexable by search engine and LLM crawlers.
        Mirrors the SEO copy in app/layout.tsx and the SoftwareApplication
        JSON-LD so the on-page text matches the structured data.
      */}
      <section
        aria-labelledby="about-heading"
        className="max-w-3xl w-full mx-auto px-4"
        style={{ marginTop: "96px" }}
      >
        <h3
          id="about-heading"
          className="text-base font-medium mb-4"
          style={{ color: "var(--color-text-muted)" }}
        >
          About Scutum Research
        </h3>
        <div
          className="text-sm leading-relaxed space-y-4"
          style={{ color: "var(--color-text-subtle)", maxWidth: "720px" }}
        >
          <p>
            Scutum Research is an AI-powered search product that returns
            interactive answers — calculators, charts, comparison tables —
            instead of walls of text. Ask any question and the answer is
            rendered as a real React component you can manipulate.
          </p>
          <p>
            Powered by Scutum, a self-hosted LLM control plane. Every query is
            auditable. Every model is swappable. Sources are cited inline.
          </p>
          <p>Free to use. No signup required. Rate-limited.</p>
          <div>
            <p className="mb-2">Common queries:</p>
            <ul className="list-disc pl-5 space-y-1">
              <li>
                &ldquo;Build me a retirement calculator with adjustable
                returns&rdquo;
              </li>
              <li>
                &ldquo;Compare Postgres vs MongoDB for a 50-person team&rdquo;
              </li>
              <li>
                &ldquo;Show me sprint velocity over the last 6 sprints&rdquo;
              </li>
            </ul>
          </div>
          <p>
            Run this on your own infrastructure:{" "}
            <a
              href="https://scutum.dev"
              className="underline hover:text-[var(--color-text)]"
            >
              scutum.dev
            </a>{" "}
            — the self-hosted gateway that powers Scutum Research.
          </p>
        </div>
      </section>

      <footer className="border-t border-[var(--color-border)] px-6 py-3 text-xs text-[var(--color-text-subtle)]" style={{ marginTop: "96px" }}>
        Powered by{" "}
        <a
          href="https://scutum.dev"
          className="underline hover:text-[var(--color-text)]"
        >
          Scutum
        </a>
        . Every query is auditable, every model is pluggable.
      </footer>
    </main>
  );
}
