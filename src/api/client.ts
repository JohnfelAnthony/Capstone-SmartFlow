function defaultApiBaseUrl() {
  if (typeof window === "undefined") return "http://127.0.0.1:8000"
  const hostname = window.location.hostname || "127.0.0.1"
  return `http://${hostname}:8000`
}

export const API_BASE_URL = import.meta.env.VITE_SMARTFLOW_API_BASE_URL ?? defaultApiBaseUrl()

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json")
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
    credentials: "include",
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  })

  if (!response.ok) {
    let message = `Request failed with status ${response.status}.`
    try {
      const payload = await response.json()
      if (typeof payload.detail === "string") {
        message = payload.detail
      }
    } catch {
      // Keep the generic message when the server did not send JSON.
    }
    throw new ApiError(response.status, message)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}

export function apiWebSocketUrl(path: string) {
  const url = new URL(path, API_BASE_URL)
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:"
  return url.toString()
}
