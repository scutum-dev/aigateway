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
      <footer className="border-t border-[var(--color-border)] px-6 py-3 text-xs text-[var(--color-text-subtle)]">
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
