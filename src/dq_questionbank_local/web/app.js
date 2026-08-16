"use strict";

const state = {
  current: null,
  selectedId: null,
  selectedQuestionIndex: 0,
  persisted: false,
  view: "empty",
  subject: "",
  type: "",
};

const setList = document.querySelector("#set-list");
const setCount = document.querySelector("#set-count");
const editorForm = document.querySelector("#editor-form");
const bankView = document.querySelector("#bank-view");
const emptyState = document.querySelector("#empty-state");
const questionList = document.querySelector("#question-list");
const questionTemplate = document.querySelector("#question-template");
const questionResults = document.querySelector("#question-results");
const status = document.querySelector("#status");
const loadCaseButton = document.querySelector("#load-case");
const bankNav = document.querySelector("#question-bank-nav");
const editorNav = document.querySelector("#editor-nav");
const searchInput = document.querySelector("#question-search");
const subjectFilter = document.querySelector("#subject-filter");
const typeFilter = document.querySelector("#type-filter");

function newQuestion(number) {
  return {
    schema_version: "1.0",
    id: `q-${number}`,
    type: "short_answer",
    language: "en",
    stem: { blocks: [{ type: "text", text: "Write a synthetic answer.", language: "en" }] },
  };
}

function contentText(content) {
  if (typeof content === "string") return content;
  if (!content || !Array.isArray(content.blocks)) return "";
  return content.blocks.map((block) => {
    if (block.type === "line_break") return "\n";
    if (block.type === "math") return `$${block.latex || ""}$`;
    if (block.type === "table") {
      return (block.rows || []).map((row) => row.join(" ")).join(" ");
    }
    return block.text || block.latex || block.alt_text || "";
  }).join("");
}

function hasStructuredBlocks(content) {
  return Boolean(content?.blocks?.some((block) => !["text", "line_break"].includes(block.type)));
}

function renderTable(container, block) {
  const figure = document.createElement("figure");
  figure.className = "question-table-figure";
  if (block.metadata?.caption) {
    const caption = document.createElement("figcaption");
    caption.textContent = block.metadata.caption;
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
}

function renderStructuredContent(container, content) {
  container.replaceChildren();
  for (const block of content?.blocks || []) {
    if (block.type === "line_break") {
      container.append(document.createElement("br"));
    } else if (block.type === "table") {
      renderTable(container, block);
    } else if (block.type === "code") {
      const code = document.createElement("pre");
      code.className = "content-code";
      code.textContent = block.text || "";
      container.append(code);
    } else {
      const element = document.createElement("span");
      element.className = `content-${block.type || "text"}`;
      if (block.type === "math" && block.metadata?.display) element.classList.add("display");
      if (block.type === "math" && globalThis.katex) {
        globalThis.katex.render(block.latex || "", element, {
          displayMode: Boolean(block.metadata?.display),
          output: "htmlAndMathml",
          strict: "warn",
          throwOnError: false,
          trust: false,
        });
      } else {
        element.textContent = block.type === "math"
          ? `\\(${block.latex || ""}\\)`
          : block.text || block.alt_text || "";
      }
      container.append(element);
    }
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

function formatType(value) {
  return String(value || "unknown").replaceAll("_", " ");
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
  setCount.textContent = String(sets.length);
  setList.replaceChildren();
  for (const item of sets) {
    const button = document.createElement("button");
    button.className = `set-item${item.id === selectId ? " active" : ""}`;
    button.type = "button";
    const title = document.createElement("strong");
    title.textContent = item.title;
    const detail = document.createElement("span");
    detail.textContent = `${item.question_count} question${item.question_count === 1 ? "" : "s"} · ${item.id}`;
    button.append(title, detail);
    button.addEventListener("click", () => loadSet(item.id));
    setList.append(button);
  }
  return sets;
}

function setView(view) {
  state.view = view;
  emptyState.hidden = view !== "empty";
  bankView.hidden = view !== "bank";
  editorForm.hidden = view !== "editor";
  bankNav.classList.toggle("active", view === "bank");
  editorNav.classList.toggle("active", view === "editor");
}

function setFilterOptions(container, selected, values, onSelect) {
  container.replaceChildren();
  const entries = ["", ...new Set(values.filter(Boolean).sort())];
  for (const value of entries) {
    const button = document.createElement("button");
    button.className = `chip${value === selected ? " active" : ""}`;
    button.type = "button";
    button.dataset.value = value;
    button.textContent = value ? formatType(value) : "All";
    button.addEventListener("click", () => onSelect(value));
    container.append(button);
  }
}

function renderFilters() {
  const questions = state.current?.questions || [];
  setFilterOptions(subjectFilter, state.subject, questions.map((item) => item.subject), (value) => {
    state.subject = value;
    renderFilters();
    renderQuestionResults();
  });
  setFilterOptions(typeFilter, state.type, questions.map((item) => item.type), (value) => {
    state.type = value;
    renderFilters();
    renderQuestionResults();
  });
}

function matchesFilters(question) {
  const search = searchInput.value.trim().toLocaleLowerCase();
  const searchable = [
    question.id,
    question.subject,
    question.type,
    question.source?.title,
    question.source?.attribution,
    question.metadata?.question_category,
    stemText(question),
    answerText(question.answer),
    contentText(question.solution),
  ].filter(Boolean).join(" ").toLocaleLowerCase();
  return (!search || searchable.includes(search))
    && (!state.subject || question.subject === state.subject)
    && (!state.type || question.type === state.type);
}

function appendTextElement(container, className, text) {
  if (!text) return;
  const element = document.createElement("span");
  element.className = className;
  element.textContent = text;
  container.append(element);
}

function makeQuestionCard(question, index) {
  const card = document.createElement("article");
  card.className = "question-card";
  card.dataset.questionIndex = String(index);

  const header = document.createElement("header");
  header.className = "question-header";
  appendTextElement(header, "question-source", question.source?.title || "Local collection");
  appendTextElement(header, "question-number", question.id || `Question ${index + 1}`);
  appendTextElement(header, "question-type", formatType(question.type));
  appendTextElement(header, "question-category", question.metadata?.question_category || "");

  const body = document.createElement("div");
  body.className = "question-body";
  const stem = document.createElement("div");
  stem.className = "question-text rendered-content";
  renderStructuredContent(stem, question.stem);
  body.append(stem);
  if (question.choices?.length) {
    const options = document.createElement("div");
    options.className = "question-options";
    for (const choice of question.choices) {
      const option = document.createElement("div");
      option.className = "option-item";
      appendTextElement(option, "option-label", choice.id);
      const content = document.createElement("div");
      content.className = "rendered-content";
      renderStructuredContent(content, choice.content);
      option.append(content);
      options.append(option);
    }
    body.append(options);
  }

  const footer = document.createElement("footer");
  footer.className = "question-footer";
  const meta = document.createElement("span");
  meta.className = "question-meta";
  meta.textContent = [question.subject, question.metadata?.grade, question.language]
    .filter(Boolean).join(" · ");
  const actions = document.createElement("div");
  actions.className = "question-actions";
  const answer = answerText(question.answer);
  const hasDetails = Boolean(answer || question.solution);
  let details = null;
  if (hasDetails) {
    const toggle = document.createElement("button");
    toggle.className = "expand-btn";
    toggle.type = "button";
    toggle.textContent = "Expand answer and solution";
    toggle.setAttribute("aria-expanded", "false");
    details = document.createElement("div");
    details.className = "question-details";
    details.hidden = true;
    if (answer) {
      const section = document.createElement("section");
      section.className = "detail-section";
      const title = document.createElement("h4");
      title.textContent = "Answer";
      const value = document.createElement("p");
      value.className = "answer-text";
      value.textContent = answer;
      section.append(title, value);
      details.append(section);
    }
    if (question.solution) {
      const section = document.createElement("section");
      section.className = "detail-section";
      const title = document.createElement("h4");
      title.textContent = "Solution";
      const value = document.createElement("div");
      value.className = "rendered-content";
      renderStructuredContent(value, question.solution);
      section.append(title, value);
      details.append(section);
    }
    toggle.addEventListener("click", () => {
      details.hidden = !details.hidden;
      toggle.setAttribute("aria-expanded", String(!details.hidden));
      toggle.textContent = details.hidden ? "Expand answer and solution" : "Collapse answer and solution";
    });
    actions.append(toggle);
  }
  const edit = document.createElement("button");
  edit.className = "expand-btn";
  edit.type = "button";
  edit.textContent = "Edit question";
  edit.addEventListener("click", () => {
    state.selectedQuestionIndex = index;
    editCurrentQuestion();
  });
  actions.append(edit);
  footer.append(meta, actions);
  card.append(header, body, footer);
  if (details) card.append(details);
  return card;
}

function renderQuestionResults() {
  const questions = state.current?.questions || [];
  const matches = questions
    .map((question, index) => ({ question, index }))
    .filter(({ question }) => matchesFilters(question));
  document.querySelector("#result-count").textContent = `${matches.length} result${matches.length === 1 ? "" : "s"}`;
  questionResults.replaceChildren();
  if (!matches.length) {
    const message = document.createElement("p");
    message.className = "no-results";
    message.textContent = "No questions match these filters.";
    questionResults.append(message);
    return;
  }
  for (const { question, index } of matches) questionResults.append(makeQuestionCard(question, index));
}

function renderBank(payload) {
  document.querySelector("#bank-title").textContent = payload.title;
  document.querySelector("#bank-description").textContent = payload.description || "";
  const subjectCount = new Set(payload.questions.map((item) => item.subject).filter(Boolean)).size;
  const typeCount = new Set(payload.questions.map((item) => item.type).filter(Boolean)).size;
  document.querySelector("#collection-meta").textContent = [
    `${payload.questions.length} questions`,
    `${subjectCount} subjects`,
    `${typeCount} types`,
    `schema ${payload.schema_version || "1.0"}`,
  ].join(" · ");
  renderFilters();
  renderQuestionResults();
}

function addQuestion(question, index = questionList.children.length) {
  const fragment = questionTemplate.content.cloneNode(true);
  const card = fragment.querySelector(".edit-question-card");
  card.dataset.questionIndex = String(index);
  card.dataset.original = JSON.stringify(question);
  card.dataset.originalStem = stemText(question);
  fragment.querySelector(".question-number").textContent = `Question ${index + 1}`;
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
  if (question.choices?.length) {
    contentArea.hidden = false;
    choicesArea.hidden = false;
    for (const choice of question.choices) {
      const row = document.createElement("div");
      row.className = "choice-row";
      appendTextElement(row, "", choice.id);
      appendTextElement(row, "", contentText(choice.content));
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
  fragment.querySelector(".remove-question").addEventListener("click", () => {
    card.remove();
    renumberQuestions();
  });
  questionList.append(fragment);
}

function renumberQuestions() {
  [...questionList.children].forEach((card, index) => {
    card.dataset.questionIndex = String(index);
    card.querySelector(".question-number").textContent = `Question ${index + 1}`;
  });
}

function populateEditor(payload) {
  document.querySelector("#editor-title").textContent = payload.title;
  document.querySelector("#set-id").value = payload.id;
  document.querySelector("#set-title").value = payload.title;
  document.querySelector("#set-description").value = payload.description || "";
  questionList.replaceChildren();
  payload.questions.forEach(addQuestion);
}

function renderWorkspace(payload, persisted = true, view = "bank") {
  state.current = payload;
  state.selectedId = payload.id;
  state.selectedQuestionIndex = Math.min(state.selectedQuestionIndex, Math.max(payload.questions.length - 1, 0));
  state.persisted = persisted;
  state.subject = "";
  state.type = "";
  editorNav.disabled = false;
  searchInput.value = "";
  populateEditor(payload);
  renderBank(payload);
  setView(view);
  setStatus("");
}

async function loadSet(id) {
  try {
    renderWorkspace(await request(`/api/sets/${encodeURIComponent(id)}`));
    await refreshList(id);
  } catch (error) {
    setStatus(error.message, true);
  }
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
    if (subject) question.subject = subject;
    else delete question.subject;
    const editedStem = card.querySelector(".question-stem").value;
    if (editedStem !== card.dataset.originalStem) {
      question.stem = { blocks: [{ type: "text", text: editedStem, language: question.language }] };
    }
    return question;
  });
  return payload;
}

function editCurrentQuestion() {
  setView("editor");
  document.querySelectorAll(".edit-question-card.target").forEach((card) => card.classList.remove("target"));
  const target = document.querySelector(`.edit-question-card[data-question-index="${state.selectedQuestionIndex}"]`);
  if (target) {
    target.classList.add("target");
    target.scrollIntoView({ behavior: "smooth", block: "center" });
  }
}

function exportCurrentSet() {
  if (!state.current) return;
  const payload = state.view === "editor" ? collectPayload() : state.current;
  const blob = new Blob([`${JSON.stringify(payload, null, 2)}\n`], { type: "application/json" });
  const link = Object.assign(document.createElement("a"), {
    href: URL.createObjectURL(blob),
    download: `${payload.id || "question-set"}.json`,
  });
  link.click();
  URL.revokeObjectURL(link.href);
}

async function loadDatabaseCase() {
  loadCaseButton.disabled = true;
  document.querySelector("#empty-load-case").disabled = true;
  try {
    const payload = await request("/api/case/load", { method: "POST" });
    renderWorkspace(payload);
    await refreshList(payload.id);
    setStatus("Public database case loaded into the question bank.");
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    loadCaseButton.disabled = false;
    document.querySelector("#empty-load-case").disabled = false;
  }
}

document.querySelector("#new-set").addEventListener("click", () => {
  renderWorkspace({
    schema_version: "1.0",
    id: "new-question-set",
    title: "New question set",
    language: "en",
    questions: [newQuestion(1)],
  }, false, "editor");
});
document.querySelector("#add-question").addEventListener("click", () => {
  addQuestion(newQuestion(questionList.children.length + 1));
});
editorForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const payload = collectPayload();
    if (state.persisted && state.selectedId !== payload.id) {
      throw new Error("Collection ID cannot be changed after saving. Create a new collection to use a different ID.");
    }
    const saved = await request(`/api/sets/${encodeURIComponent(payload.id)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    renderWorkspace(saved);
    await refreshList(saved.id);
    setStatus("Changes saved locally.");
  } catch (error) {
    setStatus(error.message, true);
  }
});
document.querySelector("#import-file").addEventListener("change", async (event) => {
  const [file] = event.target.files;
  if (!file) return;
  try {
    const payload = JSON.parse(await file.text());
    const saved = await request("/api/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    renderWorkspace(saved);
    await refreshList(saved.id);
    setStatus("JSON imported into the question bank.");
  } catch (error) {
    setStatus(error.message, true);
  }
  event.target.value = "";
});

loadCaseButton.addEventListener("click", loadDatabaseCase);
document.querySelector("#empty-load-case").addEventListener("click", loadDatabaseCase);
document.querySelector("#export-set").addEventListener("click", exportCurrentSet);
document.querySelector("#edit-set").addEventListener("click", () => setView("editor"));
document.querySelector("#back-to-bank").addEventListener("click", () => {
  populateEditor(state.current);
  setView("bank");
  setStatus("Unsaved editor changes were discarded.");
});
bankNav.addEventListener("click", () => {
  if (state.current) setView("bank");
});
editorNav.addEventListener("click", () => {
  if (state.current) setView("editor");
});
searchInput.addEventListener("input", renderQuestionResults);

async function initialize() {
  const [sets, caseInfo] = await Promise.all([refreshList(), request("/api/case")]);
  document.querySelector("#case-panel").hidden = false;
  document.querySelector("#case-title").textContent = caseInfo.title;
  document.querySelector("#case-detail").textContent = `${caseInfo.question_count} questions · ${caseInfo.license}`;
  if (sets.length) await loadSet(sets[0].id);
}

initialize().catch((error) => setStatus(error.message, true));
