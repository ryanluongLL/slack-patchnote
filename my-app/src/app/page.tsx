import { getAggregatedChangelog, ChangelogFeed } from "./changelog-feed";
import { RepoSearch } from "./repo-search";

export default async function Home() {
  const data = await getAggregatedChangelog();

  return (
    <main className="min-h-screen bg-paper text-ink">
      <div className="mx-auto max-w-3xl px-6 py-16 sm:px-10">
        <header className="mb-16 border-b border-rule pb-8">
          <p className="font-sans text-xs uppercase tracking-[0.18em] text-ink-soft">
            PatchNote
          </p>
          <h1 className="mt-2 max-w-xl font-sans text-2xl font-semibold leading-tight tracking-tight text-ink sm:text-3xl">
            What shipped, across every project, written for the people who
            use it.
          </h1>
          <p className="mt-3 max-w-xl font-sans text-sm leading-relaxed text-ink-soft">
            PatchNote watches a repository for merged pull requests, drafts
            engineering, product, and support notes automatically, and
            publishes the approved ones here. This feed combines every
            project currently connected.
          </p>

          <RepoSearch />
        </header>

        {data ? (
          <ChangelogFeed data={data} />
        ) : (
          <div className="border-t border-rule py-16 text-center">
            <p className="font-sans text-sm text-ink-soft">
              The changelog service is unreachable right now.
            </p>
          </div>
        )}

        <footer className="mt-20 border-t border-rule pt-8">
          <p className="font-sans text-xs text-ink-soft">
            Generated automatically from merged pull requests, reviewed
            before publishing.
          </p>
        </footer>
      </div>
    </main>
  );
}