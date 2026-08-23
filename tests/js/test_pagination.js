"use strict";

/*
 * Focused logic tests for the pagination control (#96):
 * - state algebra: setTotal clamps the page, setPage clamps into range;
 * - sliceFor returns exactly the current page, including the short last page;
 * - empty / loading / error / ready modes render the right controls;
 * - single-page lists hide the controls entirely;
 * - page-size changes keep the page in range;
 * - keyboard navigation moves pages via ArrowLeft / ArrowRight;
 * - page buttons and the size select drive the onChange callback.
 */

const assert = require("node:assert/strict");
const path = require("node:path");

const MODULE_PATH = path.resolve(
  __dirname, "..", "..", "src", "dq_questionbank_local", "web", "pagination.js"
);
require(MODULE_PATH);

const { createPagination, renderPaginationControls } = globalThis;

function stubElement(tagName) {
  const element = {
    tagName: String(tagName || "div").toUpperCase(),
    children: [],
    listeners: {},
    value: "",
    textContent: "",
    disabled: false,
    selected: false,
    dataset: {},
    classList: {
      classes: new Set(),
      add(name) { this.classes.add(name); },
      remove(name) { this.classes.delete(name); },
      contains(name) { return this.classes.has(name); },
    },
    append(...nodes) { this.children.push(...nodes); },
    replaceChildren(...nodes) { this.children = [...nodes]; },
    addEventListener(type, handler) {
      this.listeners[type] = this.listeners[type] || [];
      this.listeners[type].push(handler);
    },
    dispatch(type, event) {
      for (const handler of this.listeners[type] || []) handler(event);
    },
    setAttribute(name, value) { this[`attr:${name}`] = value; },
    removeAttribute(name) { delete this[`attr:${name}`]; },
  };
  return element;
}

function stubDocument() {
  return { createElement: stubElement };
}

function flatText(node) {
  const own = node.children.length ? "" : node.textContent;
  return [own, ...node.children.map(flatText)].join("");
}

function testStateAlgebra() {
  const pagination = createPagination({ pageSize: 10 });
  pagination.setTotal(95);
  assert.equal(pagination.pageCount, 10);
  pagination.setPage(99);
  assert.equal(pagination.page, 10, "setPage clamps into range");
  pagination.setPage(0);
  assert.equal(pagination.page, 1);
  pagination.setPageSize(50);
  assert.equal(pagination.pageCount, 2);
  assert.ok(pagination.page <= 2, "page stays in range after size change");
}

function testSliceForReturnsExactPages() {
  const items = Array.from({ length: 23 }, (_, index) => index);
  const pagination = createPagination({ pageSize: 10 });
  pagination.setTotal(items.length);
  assert.deepEqual(pagination.sliceFor(items), items.slice(0, 10));
  pagination.setPage(3);
  assert.deepEqual(pagination.sliceFor(items), items.slice(20, 23), "last page is short");
  pagination.setTotal(0);
  assert.equal(pagination.page, 1, "total 0 clamps back to page 1");
  assert.deepEqual(pagination.sliceFor(items), items.slice(0, 10), "window is pure paging");
}



function testEmptyModeHidesControls() {
  const pagination = createPagination({});
  const container = stubElement("div");
  pagination.setTotal(0);
  pagination.setMode("empty");
  renderPaginationControls(container, pagination, () => {}, stubDocument());
  assert.ok(container.classList.contains("hidden"));
  assert.ok(container["attr:hidden"]);
  assert.equal(container.children.length, 0);
}

function testLoadingAndErrorModesShowStatus() {
  const documentRef = stubDocument();
  const pagination = createPagination({});
  pagination.setTotal(100);
  const loading = stubElement("div");
  pagination.setMode("loading");
  renderPaginationControls(loading, pagination, () => {}, documentRef);
  assert.match(flatText(loading), /Loading/);

  const error = stubElement("div");
  pagination.setMode("error");
  renderPaginationControls(error, pagination, () => {}, documentRef);
  assert.match(flatText(error), /Could not load/);
}

function testSinglePageListHidesControls() {
  const pagination = createPagination({});
  pagination.setTotal(5);
  pagination.setMode("ready");
  const container = stubElement("div");
  renderPaginationControls(container, pagination, () => {}, stubDocument());
  assert.ok(container.classList.contains("hidden"), "one page needs no controls");
}

function testReadyModeRendersControlsAndNavigation() {
  const pagination = createPagination({ pageSize: 10 });
  pagination.setTotal(35);
  pagination.setMode("ready");
  const container = stubElement("div");
  let changes = 0;
  renderPaginationControls(container, pagination, () => { changes += 1; }, stubDocument());
  assert.ok(!container.classList.contains("hidden"));
  const [prev, pages, next] = container.children;
  assert.equal(pages.children.length, 4, "four page buttons for 35 items");
  assert.ok(prev.disabled, "prev is disabled on page 1");
  assert.ok(!next.disabled);

  next.dispatch("click", {});
  assert.equal(pagination.page, 2);
  assert.equal(changes, 1);

  pages.children[3].dispatch("click", {});
  assert.equal(pagination.page, 4);

  container.dispatch("keydown", { key: "ArrowLeft" });
  assert.equal(pagination.page, 3);
  container.dispatch("keydown", { key: "ArrowRight" });
  assert.equal(pagination.page, 4);
}

function testSizeSelectDrivesOnChange() {
  const pagination = createPagination({ pageSize: 10 });
  pagination.setTotal(100);
  pagination.setMode("ready");
  const container = stubElement("div");
  let changes = 0;
  renderPaginationControls(container, pagination, () => { changes += 1; }, stubDocument());
  const sizeSelect = container.children[container.children.length - 1];
  sizeSelect.value = "50";
  sizeSelect.dispatch("change", {});
  assert.equal(pagination.pageSize, 50);
  assert.equal(changes, 1);
}

function testUnknownModeIsRejected() {
  const pagination = createPagination({});
  assert.throws(() => pagination.setMode("sideways"), /Unknown pagination mode/);
}

function main() {
  testStateAlgebra();
  testSliceForReturnsExactPages();
  testEmptyModeHidesControls();
  testLoadingAndErrorModesShowStatus();
  testSinglePageListHidesControls();
  testReadyModeRendersControlsAndNavigation();
  testSizeSelectDrivesOnChange();
  testUnknownModeIsRejected();
  console.log("pagination checks passed");
}

main();
