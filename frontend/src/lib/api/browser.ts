import createClient from "openapi-fetch";

import type { paths } from "./schema";

/**
 * The typed API client for Client Components. It calls the frontend's own `/api` proxy, which
 * adds the signed-in user's credentials on the server, so the browser never holds them:
 *
 *     const { data, error } = await api.GET("/v1/me");
 */
export const api = createClient<paths>({ baseUrl: "/api" });
