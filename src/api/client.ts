function defaultApiBaseUrl() {
  if (typeof window === "undefined") return "http://127.0.0.1:8000"
  if (window.location.protocol === "https:") return window.location.origin
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

export const SESSION_EXPIRED_EVENT = "smartflow:session-expired"
export const SESSION_RESTORED_EVENT = "smartflow:session-restored"
let sessionExpired = false
let sessionGeneration = 0

export function sessionRestored() {
  sessionExpired = false
  sessionGeneration += 1
  if (typeof window !== "undefined") window.dispatchEvent(new Event(SESSION_RESTORED_EVENT))
}

async function apiResponse(path: string, options: RequestOptions = {}): Promise<Response> {
  const authRequest = path.startsWith("/api/auth/")
  if (sessionExpired && !authRequest) throw new ApiError(401, "Please sign in again to continue.")
  const generation = sessionGeneration
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
    if (response.status === 401 && !authRequest && generation === sessionGeneration && !sessionExpired) {
      sessionExpired = true
      if (typeof window !== "undefined") window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT))
    }
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

  return response
}

export async function apiDownload(path: string): Promise<Blob> {
  return (await apiResponse(path)).blob()
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await apiResponse(path, options)

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
