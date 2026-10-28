// @vitest-environment node
import { backendCredentials } from "./auth";

describe("backendCredentials", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("stands DEV_USER in for a signed-in user outside production", async () => {
    vi.stubEnv("NODE_ENV", "development");
    vi.stubEnv("DEV_USER", "dev-user");
    expect(await backendCredentials(new Headers())).toEqual({ "X-Dev-User": "dev-user" });
  });

  it("signs nobody in when DEV_USER is unset", async () => {
    vi.stubEnv("NODE_ENV", "development");
    vi.stubEnv("DEV_USER", "");
    expect(await backendCredentials(new Headers())).toEqual({});
  });

  it("fails closed in production, whatever DEV_USER says", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("DEV_USER", "dev-user");
    expect(await backendCredentials(new Headers({ "x-dev-user": "admin" }))).toEqual({});
  });
});
