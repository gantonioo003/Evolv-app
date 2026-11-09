import { env, hasApiConfig } from "@/config/env";

type ApiErrorPayload = {
  code?: string;
  message?: string | string[];
};

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code = "API_ERROR",
  ) {
    super(message);
  }
}

export class ApiClient {
  constructor(private readonly accessToken: string, private readonly timeoutMs = 12_000) {}

  get<T>(path: string) {
    return this.request<T>(path);
  }

  post<T>(path: string, body?: unknown) {
    return this.request<T>(path, { method: "POST", body: this.body(body) });
  }

  patch<T>(path: string, body: unknown) {
    return this.request<T>(path, { method: "PATCH", body: this.body(body) });
  }

  delete<T>(path: string) {
    return this.request<T>(path, { method: "DELETE" });
  }

  private body(value: unknown) {
    return value === undefined ? undefined : JSON.stringify(value);
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    if (!hasApiConfig) {
      throw new ApiError(
        "Defina EXPO_PUBLIC_API_URL para conectar o aplicativo ao backend.",
        0,
        "API_NOT_CONFIGURED",
      );
    }

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const response = await fetch(`${env.apiUrl}${path}`, {
        ...init,
        signal: controller.signal,
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          Authorization: `Bearer ${this.accessToken}`,
          ...init.headers,
        },
      });

      const payload = (await response.json().catch(() => null)) as
        ApiErrorPayload | T | null;

      if (!response.ok) {
        const error = payload as ApiErrorPayload | null;
        const message = Array.isArray(error?.message)
          ? error.message.join(" ")
          : error?.message;
        throw new ApiError(
          message ?? "Nao foi possivel concluir a operacao.",
          response.status,
          error?.code,
        );
      }

      return payload as T;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      if (error instanceof Error && error.name === "AbortError") {
        throw new ApiError(
          "O servidor demorou para responder.",
          0,
          "API_TIMEOUT",
        );
      }
      throw new ApiError(
        "Nao foi possivel conectar ao servidor.",
        0,
        "API_UNREACHABLE",
      );
    } finally {
      clearTimeout(timeout);
    }
  }
}
