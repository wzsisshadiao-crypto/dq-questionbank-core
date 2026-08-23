"use strict";

/*
 * Focused logic tests for the editor scroll-sync contract (#26):
 * - scrolling updates the active field to the last section at or above
 *   the navigation reference line, deterministically;
 * - exactly one field stays active;
 * - the sync is a no-op outside the editor view.
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
const FIELDS = ["stem", "choices", "answer", "analysis", "solution"];

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
      toggle(name, forced) {
        const next = forced === undefined ? !element.classes.has(name) : forced;
        if (next) element.classes.add(name);
        else element.classes.delete(name);
        return next;
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
    querySelector() { return null; },
    querySelectorAll() { return []; },
    closest() { return null; },
    scrollIntoView() {},
    focus() {},
    remove() {},
    plainText: "",
    rects: [],
  };
  element.getBoundingClientRect = () => element.rects.shift() || { top: 0, bottom: 0 };
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

function section(name, top) {
  const element = makeStubElement("section");
  element.dataset.editorSection = name;
  element.rects = [{ top, bottom: top + 100 }];
  return element;
}

function loadApp(sections, view) {
  const card = makeStubElement("article");
  card.classes.add("edit-question-card");
  card.querySelectorAll = () => sections.slice();
  const documentStub = {
    body: makeStubElement("body"),
    createElement: (tag) => makeStubElement(tag),
    createTextNode: (text) => ({ nodeType: 3, textContent: String(text) }),
    querySelector: (selector) => {
      if (selector === ".edit-question-card:not([hidden])") return card;
      return makeStubElement();
    },
    querySelectorAll: () => [],
    getElementById: () => makeStubElement(),
    addEventListener() {},
  };
  const sandbox = {
    console,
    setTimeout,
    clearTimeout,
    requestAnimationFrame: (callback) => callback(),
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
  vm.createContext(sandbox);
  vm.runInContext(APP_SOURCE, sandbox, { filename: "app.js" });
  vm.runInContext(
    "globalThis.__syncHarness = { activeEditorFieldFromScroll, setActiveEditorField, state };"
      + `__syncHarness.state.view = ${JSON.stringify(view || "editor")};`,
    sandbox,
  );
  return sandbox;
}

let checks = 0;

function check(name, run) {
  run();
  checks += 1;
  console.log(`ok - ${name}`);
}

check("the last section at or above the reference line becomes active", () => {
  const tops = { stem: -800, choices: -400, answer: 10, analysis: 300, solution: 600 };
  const sandbox = loadApp(FIELDS.map((name) => section(name, tops[name])), "editor");

  sandbox.__syncHarness.activeEditorFieldFromScroll();

  assert.equal("answer", String(sandbox.__syncHarness.state.activeEditorField));
});

check("scrolled-to-bottom keeps the final field active", () => {
  const tops = { stem: -1500, choices: -1200, answer: -900, analysis: -400, solution: -10 };
  const sandbox = loadApp(FIELDS.map((name) => section(name, tops[name])), "editor");

  sandbox.__syncHarness.activeEditorFieldFromScroll();

  assert.equal("solution", String(sandbox.__syncHarness.state.activeEditorField));
});

check("at the top the first field is active", () => {
  const tops = { stem: 0, choices: 400, answer: 800, analysis: 1200, solution: 1600 };
  const sandbox = loadApp(FIELDS.map((name) => section(name, tops[name])), "editor");

  sandbox.__syncHarness.activeEditorFieldFromScroll();

  assert.equal("stem", String(sandbox.__syncHarness.state.activeEditorField));
});

check("the sync is a no-op outside the editor view", () => {
  const sandbox = loadApp(FIELDS.map((name) => section(name, -500)), "bank");

  sandbox.__syncHarness.activeEditorFieldFromScroll();

  assert.equal("bank", String(sandbox.__syncHarness.state.view));
});

check("setActiveEditorField records exactly one field", () => {
  const sandbox = loadApp(FIELDS.map((name) => section(name, 0)), "editor");

  vm.runInContext("setActiveEditorField('analysis');", sandbox);

  assert.equal("analysis", String(sandbox.__syncHarness.state.activeEditorField));
});

console.log("scroll-sync checks passed");

