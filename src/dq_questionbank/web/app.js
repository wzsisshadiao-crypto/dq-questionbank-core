"use strict";

const sample = {
  schema_version: "1.0",
  id: "sample-set",
  title: "Original Sample Questions",
  language: "en",
  description: "Synthetic examples created for this project.",
  questions: [
    {
      schema_version: "1.0",
      id: "math-001",
      type: "single_choice",
      language: "en",
      subject: "Mathematics",
      stem: { blocks: [
        { type: "text", text: "If " },
        { type: "math", latex: "x + 3 = 7" },
        { type: "text", text: ", what is the value of " },
        { type: "math", latex: "x" },
        { type: "text", text: "?" }
      ] },
      choices: ["2", "3", "4", "5"].map((value, index) => ({
        id: String.fromCharCode(65 + index),
        content: { blocks: [{ type: "text", text: value }] }
      })),
      answer: { kind: "choice", value: "C" },
      solution: { blocks: [{ type: "math", latex: "x = 7 - 3 = 4", metadata: { display: true } }] },
      tags: ["algebra", "linear-equation"],
      difficulty: 0.2
    }
  ]
};

let questionSet = structuredClone(sample);
let selectedIndex = 0;
const editor = document.querySelector("#editor");
const preview = document.querySelector("#preview");
const validation = document.querySelector("#validation");
const status = document.querySelector("#status");

function contentText(content) {
  if (!content || !Array.isArray(content.blocks)) return "";
  return content.blocks.map(block => {
    if (block.type === "text" || block.type === "code") return block.text || "";
    if (block.type === "math") return block.metadata?.display ? `\\[${block.latex || ""}\\]` : `\\(${block.latex || ""}\\)`;
    if (block.type === "image") return `[Image: ${block.alt_text || block.asset_id || "unnamed"}]`;
    if (block.type === "table") return (block.rows || []).map(row => row.join(" | ")).join("\n");
    return "\n";
  }).join("");
}

function escapeHtml(value) {
  const element = document.createElement("span");
  element.textContent = String(value ?? "");
  return element.innerHTML;
}

function validateQuestion(question) {
  const errors = [];
  if (!question.id?.trim()) errors.push("Question id is required.");
  if (!question.type?.trim()) errors.push("Question type is required.");
  if (!Array.isArray(question.stem?.blocks)) errors.push("Stem must contain a blocks array.");
  if (["single_choice", "multiple_choice"].includes(question.type) && (!Array.isArray(question.choices) || question.choices.length < 2)) {
    errors.push("Choice questions require at least two choices.");
  }
  return errors;
}

function renderList() {
  document.querySelector("#set-title").textContent = questionSet.title || "Untitled Set";
  const list = document.querySelector("#question-list");
  list.replaceChildren(...questionSet.questions.map((question, index) => {
    const button = document.createElement("button");
    button.className = `question-item${index === selectedIndex ? " active" : ""}`;
    button.innerHTML = `<strong>${escapeHtml(question.id || `Question ${index + 1}`)}</strong>${escapeHtml(question.type || "Unknown type")}`;
    button.addEventListener("click", () => selectQuestion(index));
    return button;
  }));
}

function renderPreview(question) {
  const errors = validateQuestion(question);
  const choices = (question.choices || []).map(choice => `<li><span class="choice-id">${escapeHtml(choice.id)}</span><span>${escapeHtml(contentText(choice.content))}</span></li>`).join("");
  preview.innerHTML = `
    <p class="meta">${escapeHtml(question.subject || "General")} · ${escapeHtml(question.type || "Unknown")}</p>
    <h3>${escapeHtml(question.id || "Untitled question")}</h3>
    <p class="stem">${escapeHtml(contentText(question.stem))}</p>
    ${choices ? `<ul class="choices">${choices}</ul>` : ""}
    ${question.answer ? `<div class="answer"><strong>Answer</strong><br>${escapeHtml(JSON.stringify(question.answer.value))}</div>` : ""}`;
  validation.className = `validation${errors.length ? " error" : ""}`;
  validation.textContent = errors.length ? errors.join(" ") : "Question structure looks valid.";
}

function selectQuestion(index) {
  selectedIndex = index;
  const question = questionSet.questions[index];
  editor.value = JSON.stringify(question, null, 2);
  renderList();
  renderPreview(question);
}

editor.addEventListener("input", () => {
  try {
    const parsed = JSON.parse(editor.value);
    questionSet.questions[selectedIndex] = parsed;
    status.textContent = "Valid JSON";
    status.style.color = "var(--accent)";
    renderList();
    renderPreview(parsed);
  } catch (error) {
    status.textContent = "Invalid JSON";
    status.style.color = "var(--danger)";
    validation.className = "validation error";
    validation.textContent = error.message;
  }
});

document.querySelector("#format").addEventListener("click", () => {
  try { editor.value = JSON.stringify(JSON.parse(editor.value), null, 2); } catch (_) { /* Keep invalid input editable. */ }
});

document.querySelector("#new-question").addEventListener("click", () => {
  questionSet.questions.push({
    schema_version: "1.0",
    id: `question-${questionSet.questions.length + 1}`,
    type: "short_answer",
    language: "en",
    stem: { blocks: [{ type: "text", text: "Write the question here." }] }
  });
  selectQuestion(questionSet.questions.length - 1);
});

document.querySelector("#file-input").addEventListener("change", async event => {
  const [file] = event.target.files;
  if (!file) return;
  try {
    const parsed = JSON.parse(await file.text());
    if (!Array.isArray(parsed.questions)) throw new Error("The file must contain a questions array.");
    questionSet = parsed;
    selectedIndex = 0;
    selectQuestion(0);
    status.textContent = "File loaded";
  } catch (error) {
    status.textContent = "Load failed";
    validation.className = "validation error";
    validation.textContent = error.message;
  }
});

document.querySelector("#download").addEventListener("click", () => {
  const blob = new Blob([`${JSON.stringify(questionSet, null, 2)}\n`], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${questionSet.id || "questions"}.json`;
  link.click();
  URL.revokeObjectURL(link.href);
  status.textContent = "Downloaded";
});

selectQuestion(0);
