"use strict";

/*
 * Focused logic tests for fetchWithRetries (#96):
 * - bounded retries with exponential backoff (fake sleep records delays);
 * - AbortController timeout aborts a hanging fetch and retries;
 * - exhaustion after final failure surfaces a typed FetchRetryError;
 * - non-retryable 4xx returns the Response untouched on first attempt;
 * - success on a later attempt resolves;
 * - backoff jitter is deterministic when random is injected.
 */

const assert = require("node:assert/strict");
const path = require("node:path");

const MODULE_PATH = path.resolve(
  __dirname, "..", "..", "src", "dq_questionbank_local", "web", "fetch_with_retries.js"
);
require(MODULE_PATH);

const { fetchWithRetries, FetchRetryError, computeBackoffDelay } = globalThis;

function statusResponse(status) {
  return { status, ok: status >= 200 && status < 300 };
}

async function rejects(promise) {
  try {
    await promise;
  } catch (error) {
    return error;
  }
  throw new Error("Expected the promise to reject.");
}

async function testBackoffDelaysAreExponentialAndBounded() {
  const delays = [];
  const attempts = [];
  const settings = {
    retries: 3,
    timeoutMs: 1000,
    baseDelayMs: 100,
    maxDelayMs: 400,
    jitter: false,
    sleep: async (ms) => { delays.push(ms); },
    fetchImpl: async () => { attempts.push(1); return statusResponse(503); },
  };
  const error = await rejects(fetchWithRetries("/api/sets", {}, settings));
  assert.ok(error instanceof FetchRetryError, "exhaustion raises the typed error");
  assert.equal(error.attempts, 4);
  assert.equal(error.lastStatus, 503);
  assert.deepEqual(delays, [100, 200, 400], "backoff doubles and is capped");
  assert.equal(attempts.length, 4, "retries are strictly bounded");
}

async function testTimeoutAbortsAndRetries() {
  const delays = [];
  let aborted = 0;
  class StubController {
    constructor() {
      this.signal = {
        aborted: false,
        listeners: [],
        addEventListener(type, handler) { this.listeners.push(handler); },
      };
    }
    abort() {
      aborted += 1;
      this.signal.aborted = true;
      for (const handler of [...this.signal.listeners]) handler();
    }
  }
  const settings = {
    retries: 1,
    timeoutMs: 50,
    baseDelayMs: 10,
    jitter: false,
    AbortController: StubController,
    sleep: async (ms) => { delays.push(ms); },
    fetchImpl: (path, options) => new Promise((resolve, reject) => {
      options.signal.addEventListener("abort", () => {
        const error = new Error("The operation was aborted.");
        error.name = "AbortError";
        reject(error);
      });
    }),
  };
  const error = await rejects(fetchWithRetries("/api/sets", {}, settings));
  assert.ok(error instanceof FetchRetryError);
  assert.equal(aborted, 2, "each attempt is aborted by its timeout");
  assert.deepEqual(delays, [10]);
}

async function testSuccessOnSecondAttempt() {
  let calls = 0;
  const settings = {
    retries: 3,
    timeoutMs: 100,
    baseDelayMs: 1,
    jitter: false,
    sleep: async () => {},
    fetchImpl: async () => {
      calls += 1;
      return calls === 1 ? statusResponse(500) : statusResponse(200);
    },
  };
  const response = await fetchWithRetries("/api/sets", {}, settings);
  assert.equal(response.status, 200);
  assert.equal(calls, 2);
}

async function testClientErrorIsNotRetried() {
  let calls = 0;
  const settings = {
    retries: 3,
    timeoutMs: 100,
    baseDelayMs: 1,
    sleep: async () => {},
    fetchImpl: async () => { calls += 1; return statusResponse(404); },
  };
  const response = await fetchWithRetries("/api/missing", {}, settings);
  assert.equal(response.status, 404, "4xx returns the Response like plain fetch");
  assert.equal(calls, 1, "client errors never retry");
}

async function testNetworkErrorsRetryThenSurface() {
  const settings = {
    retries: 2,
    timeoutMs: 100,
    baseDelayMs: 1,
    jitter: false,
    sleep: async () => {},
    fetchImpl: async () => { throw new TypeError("Failed to fetch"); },
  };
  const error = await rejects(fetchWithRetries("/api/sets", {}, settings));
  assert.ok(error instanceof FetchRetryError);
  assert.equal(error.attempts, 3);
  assert.match(error.message, /TypeError: Failed to fetch/);
  assert.match(error.message, /\/api\/sets/);
}

async function testInjectedRandomMakesJitterDeterministic() {
  const delayA = computeBackoffDelay(1, { baseDelayMs: 100, maxDelayMs: 400, jitter: true, random: () => 0.5 });
  const delayB = computeBackoffDelay(1, { baseDelayMs: 100, maxDelayMs: 400, jitter: true, random: () => 0.5 });
  assert.equal(delayA, delayB);
  assert.equal(delayA, 100);
  const capped = computeBackoffDelay(9, { baseDelayMs: 100, maxDelayMs: 400, jitter: false });
  assert.equal(capped, 400, "delays cap at maxDelayMs");
}

async function main() {
  await testBackoffDelaysAreExponentialAndBounded();
  await testTimeoutAbortsAndRetries();
  await testSuccessOnSecondAttempt();
  await testClientErrorIsNotRetried();
  await testNetworkErrorsRetryThenSurface();
  await testInjectedRandomMakesJitterDeterministic();
  console.log("fetch-with-retries checks passed");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
