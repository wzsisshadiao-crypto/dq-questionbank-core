"use strict";

/*
 * Delimited-formula helpers shared by the Editor Center and the focused
 * JavaScript test suite. The module has no DOM or KaTeX dependency so the
 * insert, edit, round-trip, and recovery behavior can run under Node.js.
 */

const dqFormulaModule = (() => {
  function isEscaped(text, index) {
    let slashCount = 0;
    for (let cursor = index - 1; cursor >= 0 && text[cursor] === "\\"; cursor -= 1) {
      slashCount += 1;
    }
    return slashCount % 2 === 1;
  }

  function mathDelimiterAt(text, index) {
    if (text[index] !== "$" || isEscaped(text, index)) return "";
    if (index > 0 && text[index - 1] === "$" && !isEscaped(text, index - 1)) return "";
    return text.startsWith("$$", index) ? "$$" : "$";
  }

  function findClosingDelimiter(text, start, delimiter) {
    for (let cursor = start; cursor < text.length; cursor += 1) {
      if (mathDelimiterAt(text, cursor) === delimiter) return cursor;
    }
    return -1;
  }

  function parseDelimitedText(value) {
    const text = String(value ?? "");
    const tokens = [];
    let plainStart = 0;
    let cursor = 0;
    const pushText = (raw, start, end) => {
      if (raw) tokens.push({ type: "text", raw, start, end });
    };
    while (cursor < text.length) {
      const delimiter = mathDelimiterAt(text, cursor);
      if (!delimiter) {
        cursor += 1;
        continue;
      }
      const latexStart = cursor + delimiter.length;
      const closing = findClosingDelimiter(text, latexStart, delimiter);
      if (closing < 0 || !text.slice(latexStart, closing).trim()) {
        cursor += delimiter.length;
        continue;
      }
      pushText(text.slice(plainStart, cursor), plainStart, cursor);
      tokens.push({
        type: "math",
        latex: text.slice(latexStart, closing),
        display: delimiter === "$$",
        raw: text.slice(cursor, closing + delimiter.length),
        start: cursor,
        end: closing + delimiter.length,
      });
      cursor = closing + delimiter.length;
      plainStart = cursor;
    }
    pushText(text.slice(plainStart), plainStart, text.length);
    return tokens;
  }

  function blocksFromTokens(tokens, language = "en") {
    return tokens.map((token) => {
      if (token.type !== "math") return { type: "text", text: token.raw, language };
      return {
        type: "math",
        latex: token.latex,
        language,
        metadata: token.display ? { display: true } : {},
      };
    });
  }

  function parseEditableBlocks(value, language = "en") {
    const text = String(value ?? "");
    const tokens = parseDelimitedText(text);
    if (!tokens.length) return { blocks: [{ type: "text", text, language }] };
    return { blocks: blocksFromTokens(tokens, language) };
  }

  function formulaSource(latex, display) {
    const source = String(latex ?? "");
    return display ? `$$${source}$$` : `$${source}$`;
  }

  // Flatten canonical blocks into editable source text. Display math keeps
  // its $$ delimiters so nearby text edits preserve block boundaries and
  // display metadata on the next save.
  function flattenContent(content) {
    if (typeof content === "string") return content;
    if (!content || !Array.isArray(content.blocks)) return "";
    const parts = [];
    for (const block of content.blocks) {
      let chunk = "";
      if (block.type === "line_break") chunk = "\n";
      else if (block.type === "math") {
        chunk = formulaSource(block.latex || "", Boolean(block.metadata?.display));
      } else if (block.type === "table") {
        chunk = (block.rows || []).map((row) => row.join(" ")).join(" ");
      } else chunk = block.text || block.latex || block.alt_text || "";
      const previous = parts[parts.length - 1] ?? "";
      if (block.type === "math" && /\$$/.test(previous) && chunk.startsWith("$")) parts.push(" ");
      parts.push(chunk);
    }
    return parts.join("");
  }

  // Locate the delimited formula that contains (or touches) the caret so the
  // dialog can edit an existing block instead of inserting a duplicate.
  function findFormulaRange(value, caret) {
    const text = String(value ?? "");
    const position = Math.min(Math.max(Number(caret) || 0, 0), text.length);
    for (const token of parseDelimitedText(text)) {
      if (token.type !== "math") continue;
      if (position >= token.start && position <= token.end) {
        return { start: token.start, end: token.end, latex: token.latex, display: token.display };
      }
    }
    return null;
  }

  function replaceRange(value, start, end, latex, display) {
    const text = String(value ?? "");
    const replacement = formulaSource(latex, display);
    return {
      text: text.slice(0, start) + replacement + text.slice(end),
      start,
      end: start + replacement.length,
    };
  }

  function needsPadding(character) {
    return Boolean(character) && !/\s/.test(character);
  }

  // Insert a new formula at the caret. Spaces pad the delimiters when the
  // neighboring characters are not whitespace so plain text never glues to
  // the math block boundary.
  function insertFormula(value, caret, latex, display) {
    const text = String(value ?? "");
    const position = Math.min(Math.max(Number(caret) || 0, 0), text.length);
    const replacement = formulaSource(latex, display);
    const prefix = needsPadding(text[position - 1]) ? " " : "";
    const suffix = needsPadding(text[position]) ? " " : "";
    const next = text.slice(0, position) + prefix + replacement + suffix + text.slice(position);
    const start = position + prefix.length;
    return { text: next, start, end: start + replacement.length };
  }

  return {
    isEscaped,
    mathDelimiterAt,
    findClosingDelimiter,
    parseDelimitedText,
    blocksFromTokens,
    parseEditableBlocks,
    flattenContent,
    formulaSource,
    findFormulaRange,
    replaceRange,
    insertFormula,
  };
})();

if (typeof globalThis !== "undefined") globalThis.dqFormula = dqFormulaModule;
if (typeof module !== "undefined" && module.exports) module.exports = dqFormulaModule;
