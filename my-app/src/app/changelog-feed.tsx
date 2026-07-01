import { revalidate } from './api/changelog/feed/route';
type ChangelogEntry = {
  release_id: string;
  date: string;
  pr_count: number;
  content: string;
  repo?: string;
  display_name?: string;
};

export type ChangelogResponse = {
  repo: string;
  entries: ChangelogEntry[];
};

export async function getAggregatedChangelog(): Promise<ChangelogResponse | null> {
  const backend =
    process.env.PATCHNOTE_BACKEND_URL ?? "https://slack-patchnote.onrender.com";

  const res = await fetch(`${backend}/api/changelog/feed`, {
    next: { revalidate: 300 },
  });

  if (!res.ok) return null;
  return res.json();
}

export async function getChangelog(
  owner: string,
  repo: string
): Promise<ChangelogResponse | null> {
  const backend =
    process.env.PATCHNOTE_BACKEND_URL ?? "https://slack-patchnote.onrender.com";

  const res = await fetch(`${backend}/api/changelog/${owner}/${repo}`, {
    next: { revalidate: 300 },
  });

  if (!res.ok) return null;
  return res.json();
}

function formatDate(iso: string): { day: string; month: string; year: string } {
  const d = new Date(iso);
  return {
    day: d.toLocaleDateString("en-US", { day: "2-digit" }),
    month: d.toLocaleDateString("en-US", { month: "short" }),
    year: d.toLocaleDateString("en-US", { year: "numeric" }),
  };
}

function splitContent(content: string): { lead: string; body: string } {
  const cleaned = content.trim();
  const parts = cleaned.split(/\n\s*\n/);
  const leadRaw = parts[0] ?? "";
  const body = parts.slice(1).join("\n\n").trim();
  return { lead: leadRaw.trim(), body: body || cleaned.slice(leadRaw.length).trim() };
}

function renderInline(text: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  const pattern = /(\*[^*]+\*|(?<![\w])_[^_]+_(?![\w]))/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }
    const token = match[0];
    if (token.startsWith("*")) {
      nodes.push(<strong key={key++} className="font-semibold">{token.slice(1, -1)}</strong>);
    } else {
      nodes.push(<em key={key++}>{token.slice(1, -1)}</em>);
    }
    lastIndex = match.index + token.length;
  }
  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }
  return nodes;
}

function renderBody(body: string): React.ReactNode {
  const lines = body.split("\n").filter((l) => l.trim().length > 0);
  const blocks: React.ReactNode[] = [];
  let currentList: string[] = [];
  let blockKey = 0;

  const flushList = () => {
    if (currentList.length > 0) {
      blocks.push(
        <ul key={`list-${blockKey++}`} className="mt-4 space-y-2 pl-5">
          {currentList.map((item, i) => (
            <li key={i} className="list-disc marker:text-accent">
              {renderInline(item)}
            </li>
          ))}
        </ul>
      );
      currentList = [];
    }
  };

  for (const line of lines) {
    const bulletMatch = line.match(/^[•\-]\s+(.*)/);
    if (bulletMatch) {
      currentList.push(bulletMatch[1]);
    } else {
      flushList();
      const isHeadingLike = /^\*[^*]+\*$/.test(line.trim());
      blocks.push(
        <p
          key={`p-${blockKey++}`}
          className={isHeadingLike ? "mt-6" : "mt-3"}
        >
          {renderInline(line)}
        </p>
      );
    }
  }
  flushList();

  return blocks;
}

export function ChangelogFeed({ data }: { data: ChangelogResponse }) {
  if (data.entries.length === 0) {
    return (
      <div className="border-t border-rule py-16 text-center">
        <p className="font-sans text-sm text-ink-soft">
          Nothing has been published yet for this repository.
        </p>
      </div>
    );
  }

  return (
    <ol className="relative">
      {data.entries.map((entry) => {
        const { day, month, year } = formatDate(entry.date);
        const { lead, body } = splitContent(entry.content);

        return (
          <li
            key={entry.release_id}
            className="relative grid grid-cols-[5.5rem_1px_1fr] gap-x-6 border-t border-rule py-10 first:border-t-0 first:pt-0 sm:grid-cols-[6.5rem_1px_1fr]"
          >
            <div className="pt-1 text-right">
              <div className="font-sans text-xl font-semibold leading-none text-ink">
                {day}
              </div>
              <div className="mt-1 font-sans text-xs uppercase tracking-wide text-ink-soft">
                {month} {year}
              </div>
            </div>

            <div className="bg-rule" aria-hidden="true" />

            <div>
              <div className="mb-3 flex items-center gap-3">
                {entry.display_name && (
                  <>
                    <span className="font-sans text-[0.7rem] font-medium uppercase tracking-wide text-ink">
                        {entry.display_name}
                    </span>
                    <span className="text-ink-soft/40">.</span>
                  </>
                )}
                <span className="font-sans text-[0.7rem] font-medium uppercase tracking-wide text-accent">
                  {entry.pr_count} {entry.pr_count === 1 ? "change" : "changes" }
                </span>
              </div>

              {lead && (
                <p className="font-serif text-lg font-medium leading-snug text-ink">
                  {renderInline(lead)}
                </p>
              )}

              {body && (
                <div className="font-serif text-[0.98rem] leading-relaxed text-ink/90 [&_p:first-child]:mt-0">
                  {renderBody(body)}
                </div>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}