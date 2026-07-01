import { NextResponse } from "next/server";

const BACKEND_URL =
    process.env.PATCHNOTE_BACKEND_URL ?? "https://slack-patchnote.onrender.com";

export const revalidate = 300;

export async function GET() {
    try {
        const res = await fetch(`${BACKEND_URL}/api/changelog/feed`, {
            next: { revalidate: 300 },
        });

        if (!res.ok) {
            return NextResponse.json(
                { error: "Could not load the changelog feed right now." },
                { status: res.status }
            );
        }
        const data = await res.json();
        return NextResponse.json(data);
    } catch {
        return NextResponse.json(
            { error: "Could not reach the changelog service" },
            { status: 502 }
        );
    }
}