// Stand-in for the API in e2e tests. Echoes the method, path, query and headers it got.
import { createServer } from "node:http";

const server = createServer((request, response) => {
  if (request.url === "/healthz") {
    response.writeHead(200, { "content-type": "application/json" });
    response.end('{"status":"ok"}');
    return;
  }
  const chunks = [];
  request.on("data", (chunk) => chunks.push(chunk));
  request.on("end", () => {
    const url = new URL(request.url ?? "/", "http://stub");
    if (url.pathname === "/v1/redirect") {
      response.writeHead(302, { location: "https://example.com/" });
      response.end();
      return;
    }
    response.writeHead(url.pathname === "/v1/missing" ? 404 : 200, {
      "content-type": "application/json",
      "set-cookie": "stub=1",
      "x-internal": "should-not-leak",
    });
    response.end(
      JSON.stringify({
        method: request.method,
        path: url.pathname,
        query: url.search,
        headers: request.headers,
        body: Buffer.concat(chunks).toString("utf8"),
      }),
    );
  });
});

server.listen(4010, "127.0.0.1");
