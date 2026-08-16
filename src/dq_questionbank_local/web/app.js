"use strict";

const state = {
  current: null,
  selectedId: null,
  selectedQuestionIndex: 0,
  persisted: false,
  view: "empty",
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
    stem: { blocks: [{ type: "text", text: "Write a synthetic answer." }] },
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
          ? `\(${block.latex || ""}\)`
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

function setFilterOptions(control, label, values) {
  const selected = control.value;
  control.replaceChildren();
  const all = document.createElement("option");
  all.value = "";
  all.textContent = label;
  control.append(all);
  for (const value of [...new Set(values.filter(Boolean))].sort()) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = formatType(value);
    control.append(option);
  }
  control.value = [...control.options].some((option) => option.value === selected) ? selected : "";
}

function matchesFilters(question) {
  const search = searchInput.value.trim().toLocaleLowerCase();
  const searchable = [
    question.id,
    question.subject,
    question.type,
    question.source?.title,
    question.source?.attribution,
    stemText(question),
  ].filter(Boolean).join(" ").toLocaleLowerCase();
  return (!search || searchable.includes(search))
    && (!subjectFilter.value || question.subject === subjectFilter.value)
    && (!typeFilter.value || question.type === typeFilter.value);
}

function resultExcerpt(question) {
  return stemText(question).replace(/\s+/g, " ").trim() || "Question content is empty.";
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
    renderQuestionPreview(null);
    return;
  }
  if (!matches.some(({ index }) => index === state.selectedQuestionIndex)) {
    state.selectedQuestionIndex = matches[0].index;
  }
  for (const { question, index } of matches) {
    const button = document.createElement("button");
    button.className = `question-result${index === state.selectedQuestionIndex ? " active" : ""}`;
    button.type = "button";
    const meta = document.createElement("span");
    meta.className = "result-meta";
    const id = document.createElement("strong");
    id.textContent = question.id || `Question ${index + 1}`;
    const type = document.createElement("span");
    type.textContent = formatType(question.type);
    meta.append(id, type);
    const excerpt = document.createElement("p");
    excerpt.textContent = resultExcerpt(question);
    button.append(meta, excerpt);
    button.addEventListener("click", () => {
      state.selectedQuestionIndex = index;
      renderQuestionResults();
    });
    questionResults.append(button);
  }
  renderQuestionPreview(questions[state.selectedQuestionIndex]);
}

function addPreviewTag(value, className = "") {
  if (!value) return;
  const tag = document.createElement("span");
  tag.className = `preview-tag${className ? ` ${className}` : ""}`;
  tag.textContent = formatType(value);
  document.querySelector("#preview-tags").append(tag);
}

function renderQuestionPreview(question) {
  const empty = document.querySelector("#preview-empty");
  const detail = document.querySelector("#question-detail");
  empty.hidden = Boolean(question);
  detail.hidden = !question;
  if (!question) return;

  const index = state.current.questions.indexOf(question);
  document.querySelector("#preview-position").textContent = `QUESTION ${index + 1} OF ${state.current.questions.length}`;
  document.querySelector("#preview-id").textContent = question.id || `Question ${index + 1}`;
  const tags = document.querySelector("#preview-tags");
  tags.replaceChildren();
  addPreviewTag(question.subject || "General");
  addPreviewTag(question.type, "type");
  addPreviewTag(question.language);
  if (question.metadata?.grade) addPreviewTag(question.metadata.grade);
  if (question.metadata?.question_category) addPreviewTag(question.metadata.question_category);

  const source = document.querySelector("#preview-source");
  source.hidden = !question.source?.title;
  source.textContent = question.source?.title ? `Source: ${question.source.title}` : "";
  renderStructuredContent(document.querySelector("#preview-stem"), question.stem);

  const choicesSection = document.querySelector("#preview-choices-section");
  const choices = document.querySelector("#preview-choices");
  choices.replaceChildren();
  choicesSection.hidden = !question.choices?.length;
  for (const choice of question.choices || []) {
    const row = document.createElement("div");
    row.className = "preview-choice";
    const label = document.createElement("strong");
    label.textContent = choice.id;
    const content = document.createElement("div");
    content.className = "rendered-content";
    renderStructuredContent(content, choice.content);
    row.append(label, content);
    choices.append(row);
  }

  const answer = answerText(question.answer);
  const answerSection = document.querySelector("#preview-answer-section");
  answerSection.hidden = !answer;
  document.querySelector("#preview-answer").textContent = answer;
  const solutionSection = document.querySelector("#preview-solution-section");
  solutionSection.hidden = !question.solution;
  if (question.solution) renderStructuredContent(document.querySelector("#preview-solution"), question.solution);
  document.querySelector("#answer-panel").hidden = true;
  const answerToggle = document.querySelector("#toggle-answer");
  answerToggle.hidden = !answer && !question.solution;
  answerToggle.setAttribute("aria-expanded", "false");
  answerToggle.textContent = "Show answer and solution";
}

function renderBank(payload) {
  document.querySelector("#bank-title").textContent = payload.title;
  document.querySelector("#bank-description").textContent = payload.description || "";
  document.querySelector("#summary-total").textContent = String(payload.questions.length);
  document.querySelector("#summary-subjects").textContent = String(
    new Set(payload.questions.map((item) => item.subject).filter(Boolean)).size,
  );
  document.querySelector("#summary-types").textContent = String(
    new Set(payload.questions.map((item) => item.type).filter(Boolean)).size,
  );
  document.querySelector("#summary-schema").textContent = payload.schema_version || "1.0";
  setFilterOptions(subjectFilter, "All subjects", payload.questions.map((item) => item.subject));
  setFilterOptions(typeFilter, "All types", payload.questions.map((item) => item.type));
  renderQuestionResults();
}

function addQuestion(question, index = questionList.children.length) {
  const fragment = questionTemplate.content.cloneNode(true);
  const card = fragment.querySelector(".question-card");
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
  state.selectedQuestionIndex = Math.min(
    state.selectedQuestionIndex,
    Math.max(payload.questions.length - 1, 0),
  );
  state.persisted = persisted;
  editorNav.disabled = false;
  searchInput.value = "";
  subjectFilter.value = "";
  typeFilter.value = "";
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
      question.stem = { blocks: [{ type: "text", text: editedStem }] };
    }
    return question;
  });
  return payload;
}

function editCurrentQuestion() {
  setView("editor");
  document.querySelectorAll(".question-card.target").forEach((card) => card.classList.remove("target"));
  const target = document.querySelector(`[data-question-index="${state.selectedQuestionIndex}"]`);
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
document.querySelector("#editor-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const payload = collectPayload();
    if (state.persisted && state.selectedId !== payload.id) {
      throw new Error("Set ID cannot be changed after saving. Create a new set to use a different ID.");
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
document.querySelector("#edit-current").addEventListener("click", editCurrentQuestion);
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
for (const control of [searchInput, subjectFilter, typeFilter]) {
  control.addEventListener(control === searchInput ? "input" : "change", renderQuestionResults);
}
document.querySelector("#toggle-answer").addEventListener("click", (event) => {
  const panel = document.querySelector("#answer-panel");
  panel.hidden = !panel.hidden;
  event.currentTarget.setAttribute("aria-expanded", String(!panel.hidden));
  event.currentTarget.textContent = panel.hidden
    ? "Show answer and solution"
    : "Hide answer and solution";
});

async function initialize() {
  const [sets, caseInfo] = await Promise.all([refreshList(), request("/api/case")]);
  document.querySelector("#case-panel").hidden = false;
  document.querySelector("#case-title").textContent = caseInfo.title;
  document.querySelector("#case-detail").textContent = `${caseInfo.question_count} questions · ${caseInfo.license}`;
  if (sets.length) await loadSet(sets[0].id);
}

initialize().catch((error) => setStatus(error.message, true));
