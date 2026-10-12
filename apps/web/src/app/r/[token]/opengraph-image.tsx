import { ImageResponse } from "next/og";

import { readServerConfig } from "@/lib/config";
import { outingSize } from "@/lib/recaps";
import { fetchSharedRecap } from "@/lib/shared-recap";

// The preview chat apps show for a shared link. Anyone in the chat sees it before tapping,
// so it has no names: the crew, the headline and how many played.
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "A Popshot recap";

const HERO = "#1d4e89";
const ON_HERO = "#ffffff";
const MUTED = "#c8d8ec";
const BALL = "#d7ea4c";

export default async function Image({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const recap = await fetchSharedRecap(token, { config: readServerConfig() });
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        padding: 72,
        background: HERO,
        color: ON_HERO,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 20, fontSize: 40, fontWeight: 700 }}>
        <div
          style={{
            display: "flex",
            width: 56,
            height: 56,
            borderRadius: 12,
            border: `5px solid ${ON_HERO}`,
            position: "relative",
          }}
        >
          <div style={{ position: "absolute", left: 20, top: 0, width: 5, height: 46, background: ON_HERO }} />
          <div
            style={{
              position: "absolute",
              left: 29,
              top: 5,
              width: 15,
              height: 15,
              borderRadius: 999,
              background: BALL,
            }}
          />
        </div>
        Popshot
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        <div style={{ fontSize: 34, color: MUTED }}>{recap ? recap.crew : "Pickleball with your crew"}</div>
        <div style={{ fontSize: 72, fontWeight: 700, lineHeight: 1.1 }}>
          {recap ? recap.headline : "Keep score, plan meetups, celebrate the games."}
        </div>
      </div>
      <div style={{ fontSize: 34, color: BALL, fontWeight: 700 }}>{recap ? outingSize(recap) : ""}</div>
    </div>,
    size,
  );
}
