"use strict";

/*
 * Focused DOM-level tests for the public question-card rendering path,
 * covering the table-and-math contract from issue #27:
 * - table rows and header cells survive rendering;
 * - math blocks render through the vendored KaTeX runtime;
 * - a rendering failure keeps the source visible and removes nothing.
 *
 * app.js runs inside a Node `vm` context with a minimal DOM stub and a
 * scripted KaTeX double, so no browser or new dependency is required.
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
const FIXTURE = JSON.parse(
  fs.readFileSync(
    path.join(REPOSITORY_ROOT, "tests", "fixtures", "rendering", "table-math-question.json"),
    "utf-8",
  ),
);

const BLANK_CELL_FIXTURE = JSON.parse(
  fs.readFileSync(
    path.join(REPOSITORY_ROOT, "tests", "fixtures", "rendering", "blank-cell-table.json"),
    "utf-8",
  ),
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

function textOf(node) {
  if (node.nodeType === 3) return node.textContent;
  return node.children.map(textOf).join("");
}

function descendants(node, predicate) {
  const found = [];
  const walk = (current) => {
    for (const child of current.children || []) {
      if (child.nodeType === 3) continue;
      if (predicate(child)) found.push(child);
      walk(child);
    }
  };
  walk(node);
  return found;
}

const katexCalls = [];

function makeKatex(options) {
  return {
    render(latex, element, renderOptions) {
      katexCalls.push({ latex, mode: Boolean(renderOptions && renderOptions.displayMode) });
      if (options.throwFor && latex.includes(options.throwFor)) {
        throw new Error("scripted KaTeX failure");
      }
      element.attributes["data-katex-rendered"] = latex;
    },
  };
}

function loadApp(katexStub) {
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
  sandbox.katex = katexStub;
  vm.createContext(sandbox);
  vm.runInContext(APP_SOURCE, sandbox, { filename: "app.js" });
  return sandbox;
}

let checks = 0;

function check(name, run) {
  run();
  checks += 1;
  console.log(`ok - ${name}`);
}

const sandbox = loadApp(makeKatex({ throwFor: "\\invalid{" }));
const container = makeStubElement("div");

check("a question card keeps table rows and header cells", () => {
  sandbox.renderStructuredContent(container, FIXTURE.questions[0].stem);
  const tables = descendants(container, (node) => node.tagName === "TABLE");
  assert.equal(tables.length, 1, "the table block renders one <table>");
  assert.ok(tables[0].classes.has("question-table"));
  const headerCells = descendants(tables[0], (node) => node.tagName === "TH");
  assert.equal(headerCells.length, 2, "header_rows: 1 promotes the first row");
  assert.equal(textOf(headerCells[0]), "Outcome");
  assert.equal(textOf(headerCells[1]), "Probability");
  const bodyCells = descendants(tables[0], (node) => node.tagName === "TD");
  assert.equal(bodyCells.length, 4);
  assert.equal(textOf(bodyCells[0]), "Zero successes");
});

check("the same question renders math through the KaTeX runtime", () => {
  const math = descendants(container, (node) => node.classes.has("content-math"));
  assert.equal(
    math.length,
    3,
    "the standalone identity plus the two table-cell formulas render as content-math",
  );
  const identity = math.find(
    (node) => node.attributes["data-katex-rendered"] === "\\sum_{k=0}^{n} \\binom{n}{k} = 2^n",
  );
  assert.ok(identity, "the inline identity is rendered by the KaTeX runtime");
});

check("table cells containing math also go through KaTeX", () => {
  const rendered = katexCalls.some((entry) => entry.latex === "\\binom{n}{0}p^0(1-p)^n");
  assert.ok(rendered, "the probability cell renders its formula");
});

const failureContainer = makeStubElement("div");

check("a rendering failure keeps the source visible and the table intact", () => {
  sandbox.renderStructuredContent(failureContainer, FIXTURE.questions[1].stem);
  const math = descendants(failureContainer, (node) => node.classes.has("content-math"));
  assert.equal(math.length, 1);
  assert.ok(math[0].classes.has("math-fallback"));
  assert.equal(math[0].title, "Formula could not be rendered.");
  assert.equal(math[0].textContent, "\\(\\invalid{\\)");
  const tables = descendants(failureContainer, (node) => node.tagName === "TABLE");
  assert.equal(tables.length, 1, "the failure removes no table");
  const headerCells = descendants(tables[0], (node) => node.tagName === "TH");
  assert.equal(textOf(headerCells[0]), "Column A");
});

const blankContainer = makeStubElement("div");

check("a blank cell stays an empty cell, not a missing row or column", () => {
  sandbox.renderStructuredContent(blankContainer, BLANK_CELL_FIXTURE.questions[0].stem);
  const tables = descendants(blankContainer, (node) => node.tagName === "TABLE");
  assert.equal(tables.length, 1);
  const rows = descendants(tables[0], (node) => node.tagName === "TR");
  assert.equal(rows.length, 4, "every declared row is rendered");
  const cellsOf = (row) => descendants(row, (node) => node.tagName === "TD" || node.tagName === "TH");
  assert.deepEqual(
    rows.map((row) => cellsOf(row).length),
    [2, 2, 2, 2],
    "every row keeps both columns, including the one with a blank cell",
  );
  const runCells = cellsOf(rows[2]);
  assert.equal(textOf(runCells[0]), "Run");
  assert.equal(textOf(runCells[1]), "", "the blank cell renders empty but present");
});

console.log("rendering checks passed");

