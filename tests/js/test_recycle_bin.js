"use strict";

/*
 * Focused logic tests for the soft-delete Recycle Bin contract (#58):
 * - recycling hides a question from the active list but keeps it in the
 *   canonical payload (exports keep it until permanent delete);
 * - restoring returns it to its original position;
 * - permanent delete removes it for real and clears derived selections;
 * - recycle is idempotent.
 *
 * app.js runs inside a Node `vm` context with a minimal DOM stub.
 */

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const REPOSITORY_ROOT = path.resolve(__dirname, "..", "..");
const APP_SOURCE = fs.readFileSync(
  path.join(REPOSITORY_ROOT, "src", "dq_questionbank_local", "web", "app.js"),
  "utf-8",
);

function makeStubElement(tagName) {
  const element = {
    tagName: (tagName || "div").toUpperCase(),
    children: [],
    attributes: {},
    classes: new Set(),
    hidden: false,
    value: "",
    title: "",
    style: {},
    dataset: {},
    classList: {
      add(...names) { names.forEach((name) => element.classes.add(name)); },
      remove(...names) { names.forEach((name) => element.classes.delete(name)); },
      toggle(name) {
        if (element.classes.has(name)) element.classes.delete(name);
        else element.classes.add(name);
        return element.classes.has(name);
      },
      contains(name) { return element.classes.has(name); },
    },
    append(...nodes) { element.children.push(...nodes); },
    appendChild(node) { element.children.push(node); return node; },
    replaceChildren(...nodes) { element.children = [...nodes]; },
    addEventListener() {},
    removeEventListener() {},
    setAttribute(name, value) { element.attributes[name] = String(value); },
    getAttribute(name) { return element.attributes[name]; },
    removeAttribute(name) { delete element.attributes[name]; },
    querySelector() { return makeStubElement(); },
    querySelectorAll() { return []; },
    closest() { return null; },
    scrollIntoView() {},
    focus() {},
    remove() {},
    plainText: "",
  };
  Object.defineProperty(element, "className", {
    get() { return [...element.classes].join(" "); },
    set(value) { element.classes = new Set(String(value).split(/\s+/).filter(Boolean)); },
  });
  Object.defineProperty(element, "textContent", {
    get() { return element.plainText; },
    set(value) { element.children = []; element.plainText = String(value); },
  });
  return element;
}

function loadApp() {
  const documentStub = {
    body: makeStubElement("body"),
    createElement: (tag) => makeStubElement(tag),
    createTextNode: (text) => ({ nodeType: 3, textContent: String(text) }),
    querySelector: () => makeStubElement(),
    querySelectorAll: () => [],
    getElementById: () => makeStubElement(),
    addEventListener: () => {},
  };
  const sandbox = {
    console,
    setTimeout,
    clearTimeout,
    structuredClone,
    URL,
    Blob: class Blob {},
    fetch: () => Promise.reject(new Error("no network in tests")),
    document: documentStub,
    navigator: { language: "en" },
    addEventListener() {},
    removeEventListener() {},
    location: { origin: "http://127.0.0.1:8766", protocol: "http:" },
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  sandbox.dqFormula = require("../../src/dq_questionbank_local/web/formula.js");
  sandbox.katex = { render() { throw new Error("no katex in these tests"); } };
  vm.createContext(sandbox);
  vm.runInContext(APP_SOURCE, sandbox, { filename: "app.js" });
  return sandbox;
}

const sandbox = loadApp();
vm.runInContext(
  `
  globalThis.__recycleHarness = {
    state,
    recycleQuestion,
    restoreQuestion,
    permanentlyDeleteQuestion,
    activeQuestions,
  };
  __recycleHarness.state.current = {
    schema_version: "1.0",
    id: "recycle-demo",
    title: "Recycle demo",
    questions: [
      { id: "q-1", type: "short_answer", stem: { blocks: [{ type: "text", text: "One" }] } },
      { id: "q-2", type: "short_answer", stem: { blocks: [{ type: "text", text: "Two" }] } },
      { id: "q-3", type: "short_answer", stem: { blocks: [{ type: "text", text: "Three" }] } },
    ],
  };
  __recycleHarness.state.paperQuestionIds = ["q-2"];
  `,
  sandbox,
);
const harness = sandbox.__recycleHarness;
const { state, recycleQuestion, restoreQuestion, permanentlyDeleteQuestion, activeQuestions } = harness;

let checks = 0;

function check(name, run) {
  run();
  checks += 1;
  console.log(`ok - ${name}`);
}

const idsOf = (list) => Array.from(list || []).map((question) => String(question.id));
const listOf = (list) => Array.from(list || []).map((value) => String(value));

check("recycling hides the question but keeps the canonical payload", () => {
  recycleQuestion("q-2");
  assert.deepEqual(idsOf(activeQuestions()), ["q-1", "q-3"]);
  assert.deepEqual(listOf(state.recycleIds), ["q-2"]);
  assert.equal(state.current.questions.length, 3, "payload untouched");
  assert.deepEqual(listOf(state.paperQuestionIds), [], "paper draft drops it");
});

check("the export payload keeps recycled questions until permanent delete", () => {
  const exported = idsOf(state.current.questions);
  assert.deepEqual(exported, ["q-1", "q-2", "q-3"]);
});

check("recycling the same id twice is idempotent", () => {
  recycleQuestion("q-2");
  assert.deepEqual(listOf(state.recycleIds), ["q-2"]);
});

check("restoring returns the question to its original position", () => {
  restoreQuestion("q-2");
  assert.deepEqual(idsOf(activeQuestions()), ["q-1", "q-2", "q-3"]);
  assert.deepEqual(listOf(state.recycleIds), []);
  assert.equal(String(state.current.questions[1].id), "q-2");
});

check("permanent delete removes the question for real", () => {
  recycleQuestion("q-3");
  state.paperQuestionIds = ["q-3"];
  permanentlyDeleteQuestion("q-3");
  assert.deepEqual(idsOf(state.current.questions), ["q-1", "q-2"]);
  assert.deepEqual(listOf(state.recycleIds), []);
  assert.deepEqual(listOf(state.paperQuestionIds), []);
});

check("restoring an unknown id leaves state unchanged", () => {
  restoreQuestion("never-existed");
  assert.deepEqual(idsOf(activeQuestions()), ["q-1", "q-2"]);
});

console.log("recycle checks passed");
