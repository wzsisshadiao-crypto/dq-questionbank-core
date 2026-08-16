const state = { current: null, selectedId: null, persisted: false };
const setList = document.querySelector("#set-list");
const setCount = document.querySelector("#set-count");
const editorForm = document.querySelector("#editor-form");
const emptyState = document.querySelector("#empty-state");
const questionList = document.querySelector("#question-list");
const questionTemplate = document.querySelector("#question-template");
const status = document.querySelector("#status");
const loadCaseButton = document.querySelector("#load-case");

function newQuestion(number) {
  return { schema_version: "1.0", id: `q-${number}`, type: "short_answer", language: "en", stem: { blocks: [{ type: "text", text: "Write a synthetic answer." }] } };
}

function contentText(content) {
  if (typeof content === "string") return content;
  if (!content || !Array.isArray(content.blocks)) return "";
  return content.blocks.map((block) => {
    if (block.type === "line_break") return "\n";
    if (block.type === "math") return `$${block.latex || ""}$`;
    if (block.type === "table") {
      return (block.rows || []).map((row) => row.join("\t")).join("\n");
    }
    return block.text || block.latex || block.alt_text || "";
  }).join("");
}

function hasStructuredBlocks(content) {
  return Boolean(content?.blocks?.some((block) => !["text", "line_break"].includes(block.type)));
}

function renderStructuredContent(container, content) {
  container.replaceChildren();
  for (const block of content?.blocks || []) {
    if (block.type === "line_break") {
      container.append(document.createElement("br"));
      continue;
    }
    if (block.type === "table") {
      const figure = document.createElement("figure");
      figure.className = "question-table-figure";
      const captionText = block.metadata?.caption;
      if (captionText) {
        const caption = document.createElement("figcaption");
        caption.textContent = captionText;
        figure.append(caption);
      }
      const scroller = document.createElement("div");
      scroller.className = "question-table-scroll";
      const table = document.createElement("table");
      table.className = "question-table";
      const headerRows = Number(block.metadata?.header_rows || 0);
      const headerColumns = Number(block.metadata?.header_columns || 0);
      for (const [rowIndex, values] of (block.rows || []).entries()) {
        const row = document.createElement("tr");
        for (const [columnIndex, value] of values.entries()) {
          const isColumnHeader = rowIndex < headerRows;
          const isRowHeader = columnIndex < headerColumns;
          const cell = document.createElement(isColumnHeader || isRowHeader ? "th" : "td");
          if (isColumnHeader) cell.scope = "col";
          else if (isRowHeader) cell.scope = "row";
          cell.textContent = String(value);
          row.append(cell);
        }
        table.append(row);
      }
      scroller.append(table);
      figure.append(scroller);
      container.append(figure);
      continue;
    }
    const element = document.createElement(block.type === "code" ? "pre" : "p");
    element.className = `content-block content-${block.type || "text"}`;
    element.textContent = block.type === "math"
      ? `$${block.latex || ""}$`
      : block.text || block.alt_text || "";
    container.append(element);
  }
}

function stemText(question) {
  return contentText(question.stem);
}

function answerText(answer) {
  if (!answer) return "";
  const value = Array.isArray(answer.value) ? answer.value.join(", ") : answer.value;
  return value === undefined || value === null ? "" : String(value);
}

function setStatus(message, isError = false) {
  status.textContent = message;
  status.classList.toggle("error", isError);
}

async function request(path, options = {}) {
  const response = await fetch(path, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || "Request failed.");
  return body;
}

async function refreshList(selectId = state.selectedId) {
  const { sets } = await request("/api/sets");
  setCount.textContent = `${sets.length}`;
  setList.replaceChildren();
  for (const item of sets) {
    const button = document.createElement("button");
    button.className = `set-item${item.id === selectId ? " active" : ""}`;
    button.type = "button";
    const title = document.createElement("strong"); title.textContent = item.title;
    const detail = document.createElement("span"); detail.textContent = `${item.question_count} question${item.question_count === 1 ? "" : "s"} · ${item.id}`;
    button.append(title, detail);
    button.addEventListener("click", () => loadSet(item.id));
    setList.append(button);
  }
}

function addQuestion(question) {
  const fragment = questionTemplate.content.cloneNode(true);
  const card = fragment.querySelector(".question-card");
  card.dataset.original = JSON.stringify(question);
  card.dataset.originalStem = stemText(question);
  fragment.querySelector(".question-number").textContent = `Question ${questionList.children.length + 1}`;
  fragment.querySelector(".question-id").value = question.id || "";
  fragment.querySelector(".question-type").value = question.type || "short_answer";
  fragment.querySelector(".question-language").value = question.language || "en";
  fragment.querySelector(".question-subject").value = question.subject || "";
  fragment.querySelector(".question-stem").value = stemText(question);
  const stemPreview = fragment.querySelector(".stem-preview");
  if (hasStructuredBlocks(question.stem)) {
    stemPreview.hidden = false;
    renderStructuredContent(stemPreview, question.stem);
  }
  const contentArea = fragment.querySelector(".question-content");
  const choicesArea = fragment.querySelector(".choices-area");
  const choicesList = fragment.querySelector(".choice-list");
  if (Array.isArray(question.choices) && question.choices.length) {
    contentArea.hidden = false;
    choicesArea.hidden = false;
    for (const choice of question.choices) {
      const row = document.createElement("div");
      row.className = "choice-row";
      const label = document.createElement("strong");
      label.textContent = choice.id;
      const value = document.createElement("span");
      value.textContent = contentText(choice.content);
      row.append(label, value);
      choicesList.append(row);
    }
  }
  const answer = answerText(question.answer);
  if (answer) {
    contentArea.hidden = false;
    fragment.querySelector(".answer-area").hidden = false;
    fragment.querySelector(".answer-text").textContent = answer;
  }
  const solution = contentText(question.solution);
  if (solution) {
    contentArea.hidden = false;
    fragment.querySelector(".solution-area").hidden = false;
    fragment.querySelector(".solution-text").textContent = solution;
  }
  fragment.querySelector(".remove-question").addEventListener("click", () => { card.remove(); renumberQuestions(); });
  questionList.append(fragment);
}

function renumberQuestions() {
  [...questionList.children].forEach((card, index) => { card.querySelector(".question-number").textContent = `Question ${index + 1}`; });
}

function renderEditor(payload, persisted = true) {
  state.current = payload;
  state.selectedId = payload.id;
  state.persisted = persisted;
  emptyState.hidden = true;
  editorForm.hidden = false;
  document.querySelector("#editor-title").textContent = payload.title;
  document.querySelector("#set-id").value = payload.id;
  document.querySelector("#set-title").value = payload.title;
  document.querySelector("#set-description").value = payload.description || "";
  questionList.replaceChildren();
  payload.questions.forEach(addQuestion);
  setStatus("");
}

async function loadSet(id) {
  try { renderEditor(await request(`/api/sets/${encodeURIComponent(id)}`)); await refreshList(id); }
  catch (error) { setStatus(error.message, true); }
}

function collectPayload() {
  const payload = structuredClone(state.current);
  payload.id = document.querySelector("#set-id").value.trim();
  payload.title = document.querySelector("#set-title").value.trim();
  payload.description = document.querySelector("#set-description").value.trim();
  payload.questions = [...questionList.children].map((card) => {
    const question = JSON.parse(card.dataset.original);
    question.id = card.querySelector(".question-id").value.trim();
    question.type = card.querySelector(".question-type").value;
    question.language = card.querySelector(".question-language").value.trim();
    const subject = card.querySelector(".question-subject").value.trim();
    if (subject) question.subject = subject; else delete question.subject;
    const editedStem = card.querySelector(".question-stem").value;
    if (editedStem !== card.dataset.originalStem) {
      question.stem = { blocks: [{ type: "text", text: editedStem }] };
    }
    return question;
  });
  return payload;
}

document.querySelector("#new-set").addEventListener("click", () => renderEditor({ schema_version: "1.0", id: "new-question-set", title: "New question set", language: "en", questions: [newQuestion(1)] }, false));
document.querySelector("#add-question").addEventListener("click", () => addQuestion(newQuestion(questionList.children.length + 1)));
document.querySelector("#editor-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const payload = collectPayload();
    if (state.persisted && state.selectedId !== payload.id) throw new Error("Set ID cannot be changed after saving. Create a new set to use a different ID.");
    renderEditor(await request(`/api/sets/${encodeURIComponent(payload.id)}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }));
    await refreshList(payload.id); setStatus("Saved locally.");
  } catch (error) { setStatus(error.message, true); }
});
document.querySelector("#import-file").addEventListener("change", async (event) => {
  const [file] = event.target.files;
  if (!file) return;
  try {
    const payload = JSON.parse(await file.text());
    renderEditor(await request("/api/import", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }));
    await refreshList(payload.id); setStatus("Imported and saved locally.");
  } catch (error) { setStatus(error.message, true); }
  event.target.value = "";
});
async function loadDatabaseCase() {
  loadCaseButton.disabled = true;
  try {
    const payload = await request("/api/case/load", { method: "POST" });
    renderEditor(payload);
    await refreshList(payload.id);
    setStatus("Database case loaded into the local workspace.");
  } catch (error) { setStatus(error.message, true); }
  finally { loadCaseButton.disabled = false; }
}
loadCaseButton.addEventListener("click", loadDatabaseCase);
document.querySelector("#export-set").addEventListener("click", () => {
  const payload = collectPayload();
  const blob = new Blob([JSON.stringify(payload, null, 2) + "\n"], { type: "application/json" });
  const link = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: `${payload.id || "question-set"}.json` });
  link.click(); URL.revokeObjectURL(link.href);
});
async function initialize() {
  await refreshList();
  const caseInfo = await request("/api/case");
  document.querySelector("#case-panel").hidden = false;
  document.querySelector("#case-title").textContent = caseInfo.title;
  document.querySelector("#case-detail").textContent = `${caseInfo.question_count} questions · ${caseInfo.license}`;
}
initialize().catch((error) => setStatus(error.message, true));
