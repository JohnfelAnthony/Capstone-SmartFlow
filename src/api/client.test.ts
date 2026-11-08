import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { apiRequest, ApiError, SESSION_EXPIRED_EVENT, sessionRestored } from "./client"

beforeEach(() => { vi.stubGlobal("window", new EventTarget()); sessionRestored() })
afterEach(() => vi.unstubAllGlobals())

describe("session expiry handling", () => {
  it("stops network requests after 401, emits one sign-in event, and resumes after login", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response('{"detail":"Authentication required."}', {status:401}))
    vi.stubGlobal("fetch", fetch)
    const expired = vi.fn()
    window.addEventListener(SESSION_EXPIRED_EVENT, expired)
    await expect(apiRequest("/api/compare/pair/frames")).rejects.toMatchObject({status:401})
    await expect(apiRequest("/api/compare/pair/frames")).rejects.toBeInstanceOf(ApiError)
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(expired).toHaveBeenCalledTimes(1)
    sessionRestored()
    fetch.mockResolvedValue(new Response('{"ok":true}'))
    await expect(apiRequest("/api/compare/pair/frames")).resolves.toEqual({ok:true})
  })
  it("does not turn incorrect credentials into a session-expired event", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('{}',{status:401})))
    const expired = vi.fn()
    window.addEventListener(SESSION_EXPIRED_EVENT, expired)
    await expect(apiRequest("/api/auth/login")).rejects.toMatchObject({status:401})
    expect(expired).not.toHaveBeenCalled()
  })
  it("ignores a late old-session 401 after a successful sign-in", async () => {
    let finish!: (value: Response) => void
    const fetch = vi.fn().mockImplementationOnce(() => new Promise<Response>(resolve => { finish=resolve }))
    vi.stubGlobal("fetch", fetch)
    const pending = apiRequest("/api/compare/pair/frames")
    sessionRestored()
    finish(new Response('{}',{status:401}))
    await expect(pending).rejects.toMatchObject({status:401})
    fetch.mockResolvedValue(new Response('{"ok":true}'))
    await expect(apiRequest("/api/compare/pair/frames")).resolves.toEqual({ok:true})
  })
})
