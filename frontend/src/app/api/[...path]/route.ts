// The browser's way to the backend: /api/v1/me here is GET {API_BASE_URL}/v1/me there.
// Owned by house-template-nextjs; the work is in src/lib/api/proxy.ts.
import { forward } from "@/lib/api/proxy";
import { backendCredentials } from "@/lib/auth";

async function handle(request: Request, { params }: RouteContext<"/api/[...path]">) {
  const { path } = await params;
  return forward(request, path, {
    baseUrl: process.env.API_BASE_URL,
    credentials: await backendCredentials(request.headers),
  });
}

export { handle as DELETE, handle as GET, handle as PATCH, handle as POST, handle as PUT };
