"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export function RepoSearch() {
  const [value, setValue] = useState("");
  const [error, setError] = useState("");
  const router = useRouter();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = value.trim();
    const match = trimmed.match(/^([\w.-]+)\/([\w.-]+)$/);

    if (!match) {
      setError("Use the format owner/repo, like microsoft/vscode");
      return;
    }

    setError("");
    router.push(`/changelog/${match[1]}/${match[2]}`);
  }

  return (
    <form onSubmit={handleSubmit} className="mt-6 max-w-md">
      <label
        htmlFor="repo-search"
        className="font-sans text-xs uppercase tracking-wide text-ink-soft"
      >
        Look up a specific repository
      </label>
      <div className="mt-2 flex gap-2">
        <input
          id="repo-search"
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="owner/repo"
          className="flex-1 border border-rule bg-paper px-3 py-2 font-sans text-sm text-ink placeholder:text-ink-soft/70 focus-visible:outline-2 focus-visible:outline-accent"
        />
        <button
          type="submit"
          className="cursor-pointer border border-ink bg-ink px-4 py-2 font-sans text-sm font-medium text-paper transition-colors duration-200 hover:bg-ink/85"
        >
          View
        </button>
      </div>
      {error && (
        <p className="mt-2 font-sans text-xs text-accent">{error}</p>
      )}
    </form>
  );
}