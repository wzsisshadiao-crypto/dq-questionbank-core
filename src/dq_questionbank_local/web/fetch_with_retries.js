"use strict";

/*
 * fetchWithRetries: bounded retries, exponential backoff with jitter, and an
 * AbortController timeout for every workspace network call (#96).
 *
 * Local servers fail transiently (sqlite-locked during a save, a restart in
 * flight); those failures are retryable. Client errors are not. After the
 * final attempt the caller gets one typed error carrying everything known
 * about the failure. Dependency-free: fetch/AbortController come from the
 * platform, and tests inject their own.
 *
 * Retry policy:
 * - network errors (fetch rejects) -> retry
 * - HTTP 429 and 5xx -> retry
 * - HTTP 4xx (client error) -> never retry; the Response is returned and the
 *   caller decides (mirrors the previous plain-fetch semantics)
 * - every attempt is bounded by timeoutMs via AbortController; an abort
 *   counts as a network failure and retries
 * - delays: baseDelayMs * 2^attempt, capped at maxDelayMs, with optional
 *   full jitter (deterministic when jitter is false or random is injected)
 */

(function (global) {
  const DEFAULTS = {
    retries: 3,
    timeoutMs: 8000,
    baseDelayMs: 250,
    maxDelayMs: 4000,
    jitter: true,
  };

  class FetchRetryError extends Error {
    constructor(message, details) {
      super(message);
      this.name = "FetchRetryError";
      this.attempts = details.attempts;
      this.lastStatus = details.lastStatus;
      this.lastError = details.lastError;
      this.path = details.path;
    }
  }

  function computeBackoffDelay(attempt, settings) {
    const base = settings.baseDelayMs;
    const cap = settings.maxDelayMs;
    const raw = Math.min(base * Math.pow(2, attempt), cap);
    if (!settings.jitter) return raw;
    const random = settings.random || Math.random;
    return Math.floor(random() * raw);
  }

  function isRetryableStatus(status) {
    return status === 429 || (status >= 500 && status <= 599);
  }

  async function fetchWithRetries(path, options = {}, overrides = {}) {
    const settings = Object.assign({}, DEFAULTS, overrides);
    const fetchImpl = settings.fetchImpl || global.fetch;
    const sleep = settings.sleep || ((ms) => new Promise((resolve) => setTimeout(resolve, ms)));
    const Controller = settings.AbortController || global.AbortController;
    if (typeof fetchImpl !== "function") {
      throw new FetchRetryError("No fetch implementation available.", {
        attempts: 0, lastStatus: null, lastError: null, path,
      });
    }
    let lastStatus = null;
    let lastError = null;
    const maxAttempts = settings.retries + 1;
    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
      const controller = typeof Controller === "function" ? new Controller() : null;
      const signal = controller ? controller.signal : (options.signal || undefined);
      const timer = controller
        ? setTimeout(() => controller.abort(), settings.timeoutMs)
        : null;
      try {
        const response = await fetchImpl(path, Object.assign({}, options, { signal }));
        lastStatus = response.status;
        if (!isRetryableStatus(response.status)) {
          return response;
        }
        if (attempt === maxAttempts - 1) break;
      } catch (error) {
        lastError = error;
        if (attempt === maxAttempts - 1) break;
      } finally {
        if (timer) clearTimeout(timer);
      }
      await sleep(computeBackoffDelay(attempt, settings));
    }
    const detail = lastError
      ? `${lastError.name || "Error"}: ${lastError.message || "network failure"}`
      : `status ${lastStatus}`;
    throw new FetchRetryError(`Request to ${path} failed after ${maxAttempts} attempt(s): ${detail}`, {
      attempts: maxAttempts,
      lastStatus,
      lastError,
      path,
    });
  }

  global.fetchWithRetries = fetchWithRetries;
  global.FetchRetryError = FetchRetryError;
  global.computeBackoffDelay = computeBackoffDelay;
  global.isRetryableStatus = isRetryableStatus;
})(globalThis);
