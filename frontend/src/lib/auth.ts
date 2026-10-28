import "server-only";

/**
 * Who is calling, as the backend should hear it: the one function a project replaces when it
 * picks a sign-in provider (Supabase, Clerk, Auth0, its own sessions).
 *
 * Read the frontend's own session from the incoming request (its cookie, say), and return the
 * headers that prove the user to the backend, usually `{ Authorization: "Bearer <token>" }`.
 * Return `{}` when nobody is signed in: the backend then answers 401 on protected routes.
 *
 * Until then it fails closed. In production nobody is signed in. In development and tests,
 * `DEV_USER` stands in for a signed-in user through the backend's `X-Dev-User` header, which the
 * backend also ignores in production.
 */
export async function backendCredentials(incoming: Headers): Promise<Record<string, string>> {
  void incoming; // the request a real implementation reads its session from
  const devUser = process.env.DEV_USER;
  if (process.env.NODE_ENV !== "production" && devUser) {
    return { "X-Dev-User": devUser };
  }
  return {};
}
