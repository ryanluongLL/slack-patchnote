import { notFound } from "next/navigation";
import { getChangelog, ChangelogFeed } from "../../../changelog-feed";

export default async function ChangelogPage({
  params,
}: {
  params: Promise<{ owner: string; repo: string }>;
}) {
  const { owner, repo } = await params;
  const data = await getChangelog(owner, repo);

  if (!data) notFound();

  return (
    <main className="min-h-screen bg-paper text-ink">
      <div className="mx-auto max-w-3xl px-6 py-16 sm:px-10">
        <header className="mb-16 border-b border-rule pb-8">
          <p className="font-sans text-xs uppercase tracking-[0.18em] text-ink-soft">
            Changelog
          </p>
          <h1 className="mt-2 font-sans text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
            {data.repo}
          </h1>
          <p className="mt-3 max-w-xl font-sans text-sm leading-relaxed text-ink-soft">
            What shipped, written for the people who use it. Every entry below
            has been reviewed before publishing here.
          </p>
        </header>

        <ChangelogFeed data={data} />

        <footer className="mt-20 border-t border-rule pt-8">
          <p className="font-sans text-xs text-ink-soft">
            Generated automatically from merged pull requests, reviewed before
            publishing.
          </p>
        </footer>
      </div>
    </main>
  );
}