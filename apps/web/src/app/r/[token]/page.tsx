import type { Metadata } from "next";
import { headers } from "next/headers";
import { notFound } from "next/navigation";
import { connection } from "next/server";
import { cache } from "react";

import { SharedRecapView } from "@/components/shared-recap-view";
import { readServerConfig } from "@/lib/config";
import { outingSize } from "@/lib/recaps";
import { fetchSharedRecap } from "@/lib/shared-recap";
import { siteOrigin } from "@/lib/shares";

interface Props {
  params: Promise<{ token: string }>;
}

// The metadata and the page read the same recap once per request.
const load = cache((token: string) => fetchSharedRecap(token, { config: readServerConfig() }));

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { token } = await params;
  const recap = await load(token);
  // Absolute links for the preview image, which chat apps need, dead link or not: our
  // domain when there is one, so a forwarded header can't point them anywhere else.
  const { canonicalHost } = readServerConfig();
  const metadataBase = canonicalHost ? new URL(`https://${canonicalHost}`) : siteOrigin(await headers());
  if (!recap) {
    return { metadataBase, title: "Popshot" };
  }
  // The preview text is what chat apps show before anyone taps: no names, like the image.
  const description = `${outingSize(recap)} with ${recap.crew}.`;
  return {
    metadataBase,
    title: `${recap.headline} · Popshot`,
    description,
    openGraph: { title: recap.headline, description, siteName: "Popshot", type: "article" },
    twitter: { card: "summary_large_image", title: recap.headline, description },
  };
}

export default async function SharedRecapPage({ params }: Props) {
  // Rendered per request so its scripts get this request's CSP nonce.
  await connection();
  const { token } = await params;
  const recap = await load(token);
  if (!recap) {
    notFound();
  }
  return <SharedRecapView recap={recap} />;
}
