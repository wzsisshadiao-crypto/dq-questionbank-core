"use strict";

/*
 * Rich formula editing core (#93, slices 1-2 plus the pure heart of 4):
 * - empty {} groups become one visible placeholder character (U+2B1C-ish
 *   "⬚") inside an editable projection, with exact source<->projection
 *   offset maps;
 * - Tab / Shift+Tab jump between slot placeholders, selecting the
 *   placeholder so the next keystroke fills the slot;
 * - repairCaret restores the caret across re-renders of the projection;
 * - moveMathBlock reorders formula blocks inside a flat editable source
 *   (the pure model behind drag reordering).
 *
 * Everything here is dependency-free and deterministic. The DOM host
 * (createRichFormulaEditor) is a thin shell over the pure functions so the
 * logic is fully testable under the Node vm harness.
 */

(function (global) {
  const PLACEHOLDER = "\u2B1A"; /* ⬚ */

  function isEscaped(text, index) {
    let backslashes = 0;
    let cursor = index - 1;
    while (cursor >= 0 && text[cursor] === "\\") {
      backslashes += 1;
      cursor -= 1;
    }
    return backslashes % 2 === 1;
  }

  function findEmptySlots(latex) {
    const text = String(latex ?? "");
    const slots = [];
    for (let index = 0; index + 1 < text.length; index += 1) {
      if (text[index] === "{" && text[index + 1] === "}" && !isEscaped(text, index)) {
        slots.push({ start: index, end: index + 2 });
        index += 1;
      }
    }
    return slots;
  }

  function projectForEditing(latex) {
    const text = String(latex ?? "");
    const slots = findEmptySlots(text);
    if (!slots.length) {
      return { text, slots: [], sourceMap: buildIdentityMap(text), placeholder: PLACEHOLDER };
    }
    let out = "";
    const map = [];
    let position = 0;
    for (const slot of slots) {
      for (; position < slot.start; position += 1) {
        out += text[position];
        map.push(position);
      }
      out += PLACEHOLDER;
      map.push(slot.start);
      position = slot.end;
    }
    for (; position < text.length; position += 1) {
      out += text[position];
      map.push(position);
    }
    map.push(text.length);
    return { text: out, slots: slotPlaceholders(out), sourceMap: map, placeholder: PLACEHOLDER };
  }

  function buildIdentityMap(text) {
    const map = [];
    for (let index = 0; index <= text.length; index += 1) map.push(index);
    return map;
  }

  function slotPlaceholders(projectedText) {
    const slots = [];
    for (let index = 0; index < projectedText.length; index += 1) {
      if (projectedText[index] === PLACEHOLDER) slots.push({ start: index, end: index + 1 });
    }
    return slots;
  }

  function sourceFromProjection(projectedText) {
    return String(projectedText ?? "").split(PLACEHOLDER).join("{}");
  }

  function sourceOffsetFromProjection(projection, offset) {
    const clamped = clamp(offset, 0, projection.text.length);
    return projection.sourceMap[clamped] ?? projection.sourceMap[projection.sourceMap.length - 1];
  }

  function projectionOffsetFromSource(projection, offset) {
    const target = clamp(offset, 0, sourceLength(projection));
    let best = 0;
    for (let index = 0; index < projection.sourceMap.length; index += 1) {
      if (projection.sourceMap[index] <= target) best = index;
      else break;
    }
    return best;
  }

  function sourceLength(projection) {
    const map = projection.sourceMap;
    return map.length ? map[map.length - 1] : 0;
  }

  function clamp(value, low, high) {
    return Math.min(Math.max(Number(value) || 0, low), high);
  }

  function nextSlotOffset(projectedText, from) {
    const text = String(projectedText ?? "");
    const start = clamp(from, 0, text.length);
    const index = text.indexOf(PLACEHOLDER, start);
    return index === -1 ? null : index;
  }

  function previousSlotOffset(projectedText, from) {
    const text = String(projectedText ?? "");
    const start = clamp(from, 0, text.length);
    const index = text.lastIndexOf(PLACEHOLDER, Math.max(0, start - 1));
    return index === -1 ? null : index;
  }

  function repairCaret(previousText, offset, nextText) {
    const previous = String(previousText ?? "");
    const next = String(nextText ?? "");
    let common = 0;
    const limit = Math.min(previous.length, next.length, clamp(offset, 0, previous.length));
    while (common < limit && previous[common] === next[common]) common += 1;
    const wanted = clamp(offset, 0, previous.length);
    if (wanted <= common) return Math.min(wanted, next.length);
    let suffix = 0;
    while (
      suffix < previous.length - wanted &&
      suffix < next.length - common &&
      previous[previous.length - 1 - suffix] === next[next.length - 1 - suffix]
    ) suffix += 1;
    if (suffix > 0) return Math.min(next.length - suffix, Math.max(common, wanted - (previous.length - next.length)));
    return Math.min(wanted, next.length);
  }

  function parseTokens(value) {
    const parser = global.dqFormula && global.dqFormula.parseDelimitedText;
    if (typeof parser !== "function") return null;
    return parser(value);
  }

  function moveMathBlock(value, index, offset) {
    const tokens = parseTokens(value);
    if (!tokens) return String(value ?? "");
    const mathTokens = tokens.filter((token) => token.type === "math");
    if (index < 0 || index >= mathTokens.length || !offset) return String(value ?? "");
    const target = clamp(index + offset, 0, mathTokens.length - 1);
    if (target === index) return String(value ?? "");
    const reordered = [...mathTokens];
    reordered.splice(target, 0, reordered.splice(index, 1)[0]);
    let mathCursor = 0;
    let out = "";
    for (const token of tokens) {
      if (token.type !== "math") {
        out += token.raw;
        continue;
      }
      const raw = reordered[mathCursor].raw;
      mathCursor += 1;
      if (out.length && !/\s$/.test(out)) out += " ";
      out += raw;
    }
    return out.replace(/\s{2,}/g, " ").trim();
  }

  function createRichFormulaEditor(host, options = {}) {
    if (!host) return null;
    const onChange = typeof options.onChange === "function" ? options.onChange : () => {};
    const getLatex = typeof options.getLatex === "function" ? options.getLatex : () => "";

    function setCaret(selectionStart, selectionEnd) {
      const range = document.createRange();
      const anchor = host.firstChild || host;
      if (!host.firstChild) {
        host.textContent = "";
        range.selectNodeContents(host);
        range.collapse(true);
      } else {
        const max = host.textContent.length;
        const start = clamp(selectionStart, 0, max);
        const end = clamp(selectionEnd ?? start, start, max);
        range.setStart(anchor, start);
        range.setEnd(anchor, end);
      }
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
    }

    function caretOffset() {
      const selection = window.getSelection();
      if (!selection.rangeCount) return 0;
      const range = selection.getRangeAt(0).cloneRange();
      range.selectNodeContents(host);
      range.setEnd(selection.getRangeAt(0).endContainer, selection.getRangeAt(0).endOffset);
      return range.toString().length;
    }

    function refresh() {
      const previousText = host.textContent;
      const previousCaret = caretOffset();
      const projection2 = projectForEditing(getLatex());
      host.textContent = projection2.text;
      setCaret(repairCaret(previousText, previousCaret, projection2.text));
    }

    function jumpSlot(backwards) {
      const text = host.textContent;
      const caret = caretOffset();
      const target = backwards
        ? previousSlotOffset(text, caret)
        : nextSlotOffset(text, caret);
      if (target === null) return false;
      setCaret(target, target + 1);
      return true;
    }

    function handleInput() {
      const latex = sourceFromProjection(host.textContent);
      onChange(latex);
    }

    function handleKeyDown(event) {
      if (event.key !== "Tab") return;
      event.preventDefault();
      jumpSlot(event.shiftKey);
    }

    host.classList.add("rich-formula-host");
    host.setAttribute("role", "textbox");
    host.setAttribute("aria-multiline", "true");
    host.setAttribute("spellcheck", "false");
    host.addEventListener("input", handleInput);
    host.addEventListener("keydown", handleKeyDown);
    host.textContent = projectForEditing(getLatex()).text;

    return {
      refresh,
      jumpSlot,
      destroy() {
        host.removeEventListener("input", handleInput);
        host.removeEventListener("keydown", handleKeyDown);
      },
    };
  }

  global.dqRichEdit = {
    PLACEHOLDER,
    findEmptySlots,
    projectForEditing,
    sourceFromProjection,
    sourceOffsetFromProjection,
    projectionOffsetFromSource,
    nextSlotOffset,
    previousSlotOffset,
    repairCaret,
    moveMathBlock,
    createRichFormulaEditor,
  };
})(globalThis);

