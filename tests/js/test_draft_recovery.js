"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const REPOSITORY_ROOT = path.resolve(__dirname, "..", "..");
const SOURCE = fs.readFileSync(
  path.join(REPOSITORY_ROOT, "src", "dq_questionbank_local", "web", "draft_recovery.js"),
  "utf-8",
);

const values = new Map();
const listeners = { window: {}, document: {} };
const localStorage = {
  getItem(key) { return values.has(key) ? values.get(key) : null; },
  setItem(key, value) { values.set(key, String(value)); },
  removeItem(key) { values.delete(key); },
};

const toolbar = { insertAdjacentElement() {} };
const editorFormStub = { querySelector() { return toolbar; } };
const documentStub = {
  querySelector() { return null; },
  createElement() {
    return {
      hidden: false,
      className: "",
      children: [],
      append(...children) { this.children.push(...children); },
      setAttribute() {},
      addEventListener() {},
      querySelector() { return { textContent: "" }; },
    };
  },
  addEventListener(type, callback) { listeners.document[type] = callback; },
};

const sandbox = {
  console,
  localStorage,
  document: documentStub,
  setTimeout,
  clearTimeout,
  queueMicrotask,
  Date,
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
sandbox.addEventListener = (type, callback) => { listeners.window[type] = callback; };
vm.createContext(sandbox);
vm.runInContext(
  `
  const state = {
    editorDirty: false,
    saveInFlight: false,
    view: "bank",
    current: null,
    selectedId: "set-a",
  };
  const editorForm = globalThis.__editorForm;
  function setEditorDirty(dirty) { state.editorDirty = dirty; }
  function renderWorkspace(payload) { state.current = payload; state.selectedId = payload.id; return payload; }
  function populateEditor() {}
  function collectPayload() { return state.current; }
  function setStatus() {}
  globalThis.__state = state;
  `,
  Object.assign(sandbox, { __editorForm: editorFormStub }),
);
vm.runInContext(SOURCE, sandbox, { filename: "draft_recovery.js" });

const recovery = sandbox.dqDraftRecovery;
const state = sandbox.__state;
let checks = 0;

function check(name, run) {
  run();
  checks += 1;
  console.log(`ok - ${name}`);
}

check("drafts are collection scoped", () => {
  const payload = { id: "set-a", questions: [{ id: "q-1" }] };
  assert.equal(recovery.writeDraft("set-a", payload), true);
  assert.deepEqual(JSON.parse(JSON.stringify(recovery.readDraft("set-a").payload)), payload);
  assert.equal(recovery.readDraft("set-b"), null);
});

check("corrupt drafts fail closed and are removed", () => {
  const key = recovery.storageKey("set-bad");
  localStorage.setItem(key, "{not json");
  assert.equal(recovery.readDraft("set-bad"), null);
  assert.equal(localStorage.getItem(key), null);
});

check("invalid draft shape is ignored and removed", () => {
  const key = recovery.storageKey("set-invalid");
  localStorage.setItem(key, JSON.stringify({ version: 1, collectionId: "set-invalid" }));
  assert.equal(recovery.readDraft("set-invalid"), null);
  assert.equal(localStorage.getItem(key), null);
});

check("clearDraft only removes the selected collection", () => {
  recovery.writeDraft("set-a", { id: "set-a", questions: [] });
  recovery.writeDraft("set-b", { id: "set-b", questions: [] });
  recovery.clearDraft("set-a");
  assert.equal(recovery.readDraft("set-a"), null);
  assert.notEqual(recovery.readDraft("set-b"), null);
});

check("beforeunload protects dirty state even during save-in-flight", () => {
  state.editorDirty = true;
  state.saveInFlight = true;
  const event = {
    prevented: false,
    returnValue: undefined,
    preventDefault() { this.prevented = true; },
  };
  listeners.window.beforeunload(event);
  assert.equal(event.prevented, true);
  assert.equal(event.returnValue, "");
});

check("beforeunload leaves clean state alone", () => {
  state.editorDirty = false;
  const event = {
    prevented: false,
    returnValue: undefined,
    preventDefault() { this.prevented = true; },
  };
  listeners.window.beforeunload(event);
  assert.equal(event.prevented, false);
});

console.log(`draft recovery checks passed (${checks})`);
