"use strict";

const state = {
  current: null,
  selectedId: null,
  selectedQuestionIndex: 0,
  persisted: false,
  view: "empty",
  subject: "",
  type: "",
  sets: [],
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
const searchScope = document.querySelector("#question-search-scope");
const yearInput = document.querySelector("#question-year");
const collectionSearch = document.querySelector("#collection-search");
const subjectFilter = document.querySelector("#subject-filter");
const typeFilter = document.querySelector("#type-filter");
const editorQuestionSelect = document.querySelector("#editor-question-select");

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

function renderSetList(selectId = state.selectedId) {
  const query = collectionSearch.value.trim().toLocaleLowerCase();
  const sets = state.sets.filter((item) => !query || [item.title, item.id]
    .filter(Boolean)
    .join(" ")
    .toLocaleLowerCase()
    .includes(query));
  setCount.textContent = query ? `${sets.length}/${state.sets.length}` : String(state.sets.length);
  setList.replaceChildren();
  if (!sets.length) {
    const message = document.createElement("p");
    message.className = "set-list-empty";
    message.textContent = "No collections match this search.";
    setList.append(message);
    return;
  }
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
}

async function refreshList(selectId = state.selectedId) {
  const { sets } = await request("/api/sets");
  state.sets = sets;
  renderSetList(selectId);
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
  const fields = {
    id: [question.id],
    source: [question.source?.title, question.source?.author, question.source?.attribution, question.source?.locator],
    stem: [stemText(question)],
    choices: (question.choices || []).flatMap((choice) => [choice.id, contentText(choice.content)]),
    answer: [answerText(question.answer)],
    analysis: [question.metadata?.analysis],
    solution: [contentText(question.solution)],
  };
  const scopedValues = searchScope.value === "all"
    ? Object.values(fields).flat()
    : fields[searchScope.value] || [];
  const searchable = [
    ...scopedValues,
    ...(searchScope.value === "all" ? [question.subject, question.type, question.metadata?.question_category] : []),
  ].filter(Boolean).join(" ").toLocaleLowerCase();
  const year = yearInput.value.trim();
  const questionYear = question.source?.year ?? question.metadata?.year ?? "";
  return (!search || searchable.includes(search))
    && (!year || String(questionYear) === year)
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
  card.dataset.originalAnswer = answerText(question.answer);
  card.dataset.originalAnalysis = String(question.metadata?.analysis || "");
  card.dataset.originalSolution = contentText(question.solution);
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
  const choicesArea = fragment.querySelector(".choices-area");
  const choicesList = fragment.querySelector(".choice-list");
  if (question.choices?.length) {
    choicesArea.querySelector(".field-empty").hidden = true;
    for (const choice of question.choices) {
      const row = document.createElement("div");
      row.className = "choice-row";
      appendTextElement(row, "", choice.id);
      appendTextElement(row, "", contentText(choice.content));
      choicesList.append(row);
    }
  }
  const answer = answerText(question.answer);
  fragment.querySelector(".question-answer").value = answer;
  fragment.querySelector(".question-analysis").value = question.metadata?.analysis || "";
  const solution = contentText(question.solution);
  fragment.querySelector(".question-solution").value = solution;
  fragment.querySelector(".remove-question").addEventListener("click", () => {
    if (questionList.children.length === 1) {
      setStatus("A collection must contain at least one question.", true);
      return;
    }
    card.remove();
    state.selectedQuestionIndex = Math.min(state.selectedQuestionIndex, questionList.children.length - 1);
    renumberQuestions();
    updateEditorSelection();
  });
  questionList.append(fragment);
}

function renumberQuestions() {
  [...questionList.children].forEach((card, index) => {
    card.dataset.questionIndex = String(index);
    card.querySelector(".question-number").textContent = `Question ${index + 1}`;
  });
  editorQuestionSelect.replaceChildren();
  [...questionList.children].forEach((card, index) => {
    const option = document.createElement("option");
    option.value = String(index);
    option.textContent = `${index + 1}. ${card.querySelector(".question-id").value || "Untitled question"}`;
    editorQuestionSelect.append(option);
  });
}

function updateEditorSelection() {
  const cards = [...questionList.children];
  state.selectedQuestionIndex = Math.min(Math.max(state.selectedQuestionIndex, 0), Math.max(cards.length - 1, 0));
  cards.forEach((card, index) => {
    const selected = index === state.selectedQuestionIndex;
    card.hidden = !selected;
    card.classList.toggle("target", selected);
  });
  editorQuestionSelect.value = String(state.selectedQuestionIndex);
  document.querySelector("#editor-position").textContent = cards.length
    ? `Question ${state.selectedQuestionIndex + 1} of ${cards.length}`
    : "No question selected";
  document.querySelector("#previous-question").disabled = state.selectedQuestionIndex === 0;
  document.querySelector("#next-question").disabled = state.selectedQuestionIndex >= cards.length - 1;
  for (const button of document.querySelectorAll(".remove-question")) button.disabled = cards.length === 1;
}

function populateEditor(payload) {
  document.querySelector("#editor-title").textContent = payload.title;
  document.querySelector("#set-id").value = payload.id;
  document.querySelector("#set-title").value = payload.title;
  document.querySelector("#set-description").value = payload.description || "";
  questionList.replaceChildren();
  payload.questions.forEach(addQuestion);
  renumberQuestions();
  updateEditorSelection();
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
  searchScope.value = "all";
  yearInput.value = "";
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
    const editedAnswer = card.querySelector(".question-answer").value;
    if (editedAnswer !== card.dataset.originalAnswer) {
      if (editedAnswer) {
        question.answer = typeof question.answer === "object" && question.answer !== null
          ? { ...question.answer, value: editedAnswer }
          : { kind: "text", value: editedAnswer };
      } else {
        delete question.answer;
      }
    }
    const editedAnalysis = card.querySelector(".question-analysis").value;
    if (editedAnalysis !== card.dataset.originalAnalysis) {
      question.metadata = { ...(question.metadata || {}) };
      if (editedAnalysis) question.metadata.analysis = editedAnalysis;
      else delete question.metadata.analysis;
      if (!Object.keys(question.metadata).length) delete question.metadata;
    }
    const editedSolution = card.querySelector(".question-solution").value;
    if (editedSolution !== card.dataset.originalSolution) {
      if (editedSolution) {
        question.solution = { blocks: [{ type: "text", text: editedSolution, language: question.language }] };
      } else {
        delete question.solution;
      }
    }
    return question;
  });
  return payload;
}

function editCurrentQuestion() {
  setView("editor");
  updateEditorSelection();
  document.querySelector(".edit-question-card:not([hidden])")?.scrollIntoView({ behavior: "smooth", block: "start" });
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
  state.selectedQuestionIndex = questionList.children.length - 1;
  renumberQuestions();
  updateEditorSelection();
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
  if (state.current) {
    setView("editor");
    updateEditorSelection();
  }
});
searchInput.addEventListener("input", renderQuestionResults);
searchScope.addEventListener("change", renderQuestionResults);
yearInput.addEventListener("input", renderQuestionResults);
collectionSearch.addEventListener("input", () => renderSetList());
editorQuestionSelect.addEventListener("change", () => {
  state.selectedQuestionIndex = Number(editorQuestionSelect.value);
  updateEditorSelection();
});
document.querySelector("#previous-question").addEventListener("click", () => {
  state.selectedQuestionIndex -= 1;
  updateEditorSelection();
});
document.querySelector("#next-question").addEventListener("click", () => {
  state.selectedQuestionIndex += 1;
  updateEditorSelection();
});
document.querySelector("#editor-field-nav").addEventListener("click", (event) => {
  const button = event.target.closest("[data-editor-field]");
  if (!button) return;
  const card = document.querySelector(".edit-question-card:not([hidden])");
  card?.querySelector(`[data-editor-section="${button.dataset.editorField}"]`)
    ?.scrollIntoView({ behavior: "smooth", block: "start" });
});
questionList.addEventListener("input", (event) => {
  if (!event.target.matches(".question-id")) return;
  const selectedOption = editorQuestionSelect.options[state.selectedQuestionIndex];
  if (selectedOption) selectedOption.textContent = `${state.selectedQuestionIndex + 1}. ${event.target.value || "Untitled question"}`;
});

const moreNavToggle = document.querySelector("#more-nav-toggle");
const moreNavMenu = document.querySelector("#more-nav-menu");
function setMoreMenu(open) {
  moreNavMenu.hidden = !open;
  moreNavToggle.setAttribute("aria-expanded", String(open));
}
moreNavToggle.addEventListener("click", () => setMoreMenu(moreNavMenu.hidden));
document.addEventListener("click", (event) => {
  if (!event.target.closest("#more-nav")) setMoreMenu(false);
});
document.querySelector("#theme-toggle").addEventListener("click", (event) => {
  const dark = document.body.classList.toggle("dark-theme");
  event.currentTarget.textContent = dark ? "Light theme" : "Dark theme";
});

async function initialize() {
  const [sets, caseInfo] = await Promise.all([refreshList(), request("/api/case")]);
  document.querySelector("#case-panel").hidden = false;
  document.querySelector("#case-title").textContent = caseInfo.title;
  document.querySelector("#case-detail").textContent = `${caseInfo.question_count} questions · ${caseInfo.license}`;
  if (sets.length) await loadSet(sets[0].id);
}

initialize().catch((error) => setStatus(error.message, true));
