import "server-only";

import { headers } from "next/headers";
import createClient from "openapi-fetch";

import { backendCredentials } from "@/lib/auth";

import type { paths } from "./schema";

/**
 * The typed API client for Server Components, Server Actions and Route Handlers. It calls
 * `API_BASE_URL` directly, as the signed-in user:
 *
 *     const api = await serverApi();
 *     const { data, error } = await api.GET("/v1/me");
 *
 * Reading the request makes the caller dynamic: under Cache Components, render it inside
 * `<Suspense>`.
 */
export async function serverApi() {
  const baseUrl = process.env.API_BASE_URL;
  if (!baseUrl) throw new Error("API_BASE_URL is not set: see frontend/.env.example.");
  return createClient<paths>({ baseUrl, headers: await backendCredentials(await headers()) });
}
