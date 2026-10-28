// The container's liveness check (compose.yaml, the platform's probe): answers while the server
// runs, without calling the backend, and names the commit the image was built from. The backend's
// own checks are at /api/health/*. The response is prerendered, so GIT_COMMIT is read by
// `next build` (the Dockerfile's build argument), not by the running server.
export function GET() {
  return Response.json({ status: "ok", commit: process.env.GIT_COMMIT || null });
}
