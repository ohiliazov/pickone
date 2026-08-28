export type UserOut = {
  id: string;
  email: string | null;
  email_verified: boolean;
  is_guest: boolean;
  is_admin: boolean;
};

export type ItemSummary = {
  id: string;
  text: string;
  slug: string;
  status: string;
  rating: number;
};

export type ModerationQueueItem = {
  id: string;
  text: string;
  slug: string;
  status: string;
  created_at: string;
  created_by_user_id: string | null;
  latest_scores: Record<string, number>;
  latest_provider: string | null;
};

export type ModerationQueueResponse = {
  items: ModerationQueueItem[];
};

export type ReportEntry = {
  id: string;
  reporter_user_id: string | null;
  reason: string;
  created_at: string;
};

export type ReportedItemGroup = {
  item: ItemSummary;
  reports: ReportEntry[];
};

export type ReportsResponse = {
  reports: ReportedItemGroup[];
};

export type ApiErrorBody = {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
};

export class ApiError extends Error {
  code: string;
  details: Record<string, unknown>;
  status: number;

  constructor(status: number, body: ApiErrorBody) {
    super(body.error.message);
    this.code = body.error.code;
    this.details = body.error.details;
    this.status = status;
  }
}

let csrfToken: string | null = null;

export function setCsrfToken(token: string | null) {
  csrfToken = token;
}

export function getCsrfToken(): string | null {
  return csrfToken;
}

const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export async function apiFetch<T>(
  path: string,
  options: { method?: string; body?: unknown } = {},
): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = {};

  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (UNSAFE_METHODS.has(method) && csrfToken) {
    headers["X-PickOne-CSRF"] = csrfToken;
  }

  const response = await fetch(path, {
    method,
    headers,
    credentials: "include",
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") ?? "";
  const data = contentType.includes("application/json") ? await response.json() : undefined;

  if (!response.ok) {
    throw new ApiError(response.status, data as ApiErrorBody);
  }

  return data as T;
}
