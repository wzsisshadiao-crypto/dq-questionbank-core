"use strict";

/*
 * createPagination: a generic, dependency-free paginated list control (#96).
 *
 * The state object is pure bookkeeping (total, page, pageSize, mode) with a
 * small algebra: setTotal clamps the page into range, setPage clamps into
 * [1, pageCount], sliceFor(items) returns exactly the current page, and the
 * mode tracks empty / loading / error / ready so callers never guess what a
 * missing list means. renderPaginationControls projects the state onto DOM
 * controls (prev/next, page numbers, page-size select) and wires keyboard
 * navigation (ArrowLeft / ArrowRight) on the container.
 */

(function (global) {
  const PAGE_SIZES = [10, 25, 50, 100];
  const MODES = ["empty", "loading", "error", "ready"];

  function clamp(value, low, high) {
    return Math.min(Math.max(value, low), high);
  }

  function createPagination(initial = {}) {
    const state = {
      total: 0,
      page: 1,
      pageSize: initial.pageSize || 25,
      pageSizes: initial.pageSizes || PAGE_SIZES,
      mode: "empty",
    };
    if (!state.pageSizes.includes(state.pageSize)) {
      state.pageSizes = [state.pageSize, ...state.pageSizes].sort((a, b) => a - b);
    }
    return {
      get page() { return state.page; },
      get pageSize() { return state.pageSize; },
      get total() { return state.total; },
      get mode() { return state.mode; },
      get pageCount() { return Math.max(1, Math.ceil(state.total / state.pageSize)); },
      setTotal(total) {
        state.total = Math.max(0, Math.floor(total));
        state.page = clamp(state.page, 1, this.pageCount);
        return this;
      },
      setPage(page) {
        state.page = clamp(Math.floor(page), 1, this.pageCount);
        return this;
      },
      nextPage() { return this.setPage(state.page + 1); },
      previousPage() { return this.setPage(state.page - 1); },
      setPageSize(size) {
        const next = Math.floor(size);
        if (next > 0) {
          state.pageSize = next;
          if (!state.pageSizes.includes(next)) {
            state.pageSizes = [...state.pageSizes, next].sort((a, b) => a - b);
          }
          state.page = clamp(state.page, 1, this.pageCount);
        }
        return this;
      },
      setMode(mode) {
        if (!MODES.includes(mode)) throw new Error(`Unknown pagination mode: ${mode}.`);
        state.mode = mode;
        return this;
      },
      sliceFor(items) {
        const start = (state.page - 1) * state.pageSize;
        return items.slice(start, start + state.pageSize);
      },
      pageSizes() { return [...state.pageSizes]; },
    };
  }

  function renderPaginationControls(container, pagination, onPageChange, doc) {
    const documentRef = doc || global.document;
    if (!container) return;
    container.replaceChildren();
    show(container);
    if (pagination.mode === "loading") {
      container.append(textNode(documentRef, "Loading…"));
      return;
    }
    if (pagination.mode === "error") {
      container.append(textNode(documentRef, "Could not load this list."));
      return;
    }
    if (pagination.mode === "empty" || pagination.pageCount <= 1) {
      hide(container);
      return;
    }
    const prev = button(documentRef, "‹ Prev", pagination.page <= 1, () => {
      pagination.previousPage();
      onPageChange();
    });
    const next = button(documentRef, "Next ›", pagination.page >= pagination.pageCount, () => {
      pagination.nextPage();
      onPageChange();
    });
    const pages = documentRef.createElement("span");
    pages.className = "pagination-pages";
    for (let number = 1; number <= pagination.pageCount; number += 1) {
      const pageButton = button(documentRef, String(number), number === pagination.page, () => {
        pagination.setPage(number);
        onPageChange();
      });
      if (number === pagination.page) pageButton.className = "pagination-page active";
      pages.append(pageButton);
    }
    const sizeSelect = documentRef.createElement("select");
    sizeSelect.className = "pagination-size";
    sizeSelect.setAttribute("aria-label", "Questions per page");
    for (const size of pagination.pageSizes()) {
      const option = documentRef.createElement("option");
      option.value = String(size);
      option.textContent = `${size} / page`;
      if (size === pagination.pageSize) option.selected = true;
      sizeSelect.append(option);
    }
    sizeSelect.addEventListener("change", () => {
      pagination.setPageSize(Number(sizeSelect.value));
      onPageChange();
    });
    container.append(prev, pages, next, sizeSelect);
    container.addEventListener("keydown", (event) => {
      if (event.key === "ArrowLeft" && pagination.page > 1) {
        pagination.previousPage();
        onPageChange();
      } else if (event.key === "ArrowRight" && pagination.page < pagination.pageCount) {
        pagination.nextPage();
        onPageChange();
      }
    });
  }

  function show(container) {
    container.classList.remove("hidden");
    if (container.removeAttribute) container.removeAttribute("hidden");
  }

  function hide(container) {
    container.classList.add("hidden");
    if (container.setAttribute) container.setAttribute("hidden", "hidden");
  }

  function button(documentRef, label, disabled, onClick) {
    const element = documentRef.createElement("button");
    element.type = "button";
    element.className = "pagination-page";
    element.textContent = label;
    element.disabled = disabled;
    element.addEventListener("click", onClick);
    return element;
  }

  function textNode(documentRef, message) {
    const span = documentRef.createElement("span");
    span.className = "pagination-status";
    span.textContent = message;
    return span;
  }

  global.createPagination = createPagination;
  global.renderPaginationControls = renderPaginationControls;
  global.PAGINATION_PAGE_SIZES = PAGE_SIZES;
})(globalThis);
