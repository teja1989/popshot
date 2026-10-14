import { ImageResponse } from "next/og";

// App icons, drawn at build time: a ball on the court-green background.
const SIZES = ["192", "512"] as const;
type Size = (typeof SIZES)[number];

export const dynamic = "force-static";

export function generateStaticParams(): { size: Size }[] {
  return SIZES.map((size) => ({ size }));
}

export async function GET(
  _request: Request,
  context: { params: Promise<{ size: string }> },
): Promise<Response> {
  const { size } = await context.params;
  if (!(SIZES as readonly string[]).includes(size)) {
    return new Response("Not found", { status: 404 });
  }
  const px = Number(size);
  const ball = Math.round(px * 0.46);
  const hole = Math.max(4, Math.round(px * 0.05));
  const holes = [
    [0.3, 0.32],
    [0.62, 0.3],
    [0.46, 0.52],
    [0.28, 0.66],
    [0.66, 0.66],
  ] as const;
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#1f6b5a",
        }}
      >
        <div
          style={{
            width: ball,
            height: ball,
            borderRadius: "50%",
            background: "#d7ea4c",
            position: "relative",
            display: "flex",
          }}
        >
          {holes.map(([x, y]) => (
            <div
              key={`${String(x)}-${String(y)}`}
              style={{
                position: "absolute",
                left: Math.round(ball * x - hole / 2),
                top: Math.round(ball * y - hole / 2),
                width: hole,
                height: hole,
                borderRadius: "50%",
                background: "#b6c93a",
              }}
            />
          ))}
        </div>
      </div>
    ),
    { width: px, height: px },
  );
}
