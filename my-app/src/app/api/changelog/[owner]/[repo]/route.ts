import { NextResponse } from "next/server";

const BACKEND_URL =
  process.env.PATCHNOTE_BACKEND_URL ?? "https://slack-patchnote.onrender.com";

export const revalidate = 300; // cache for 5 minutes; release notes don't change often

export async function GET(
  request: Request,
  { params }: { params: Promise<{ owner: string; repo: string }> }
) {
  const { owner, repo } = await params;

  try {
    const res = await fetch(
      `${BACKEND_URL}/api/changelog/${owner}/${repo}`,
      { next: { revalidate: 300 } }
    );

    if (!res.ok) {
      return NextResponse.json(
        { error: "Could not load this changelog right now." },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json(
      { error: "Could not reach the changelog service." },
      { status: 502 }
    );
  }
}