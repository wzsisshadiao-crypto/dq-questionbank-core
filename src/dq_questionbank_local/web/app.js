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
  paperQuestionIds: [],
  qualityFindings: [],
  qualityFilter: "all",
  qualityHasRun: false,
  reviewedQuestionIds: [],
  importSummary: null,
  editorDirty: false,
  saveInFlight: false,
};

const setList = document.querySelector("#set-list");
const setCount = document.querySelector("#set-count");
const editorForm = document.querySelector("#editor-form");
const bankView = document.querySelector("#bank-view");
const emptyState = document.querySelector("#empty-state");
const caseLoadError = document.querySelector("#case-load-error");
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
const paperView = document.querySelector("#paper-view");
const importView = document.querySelector("#import-view");
const dataView = document.querySelector("#data-view");
const qualityView = document.querySelector("#quality-view");
const reviewView = document.querySelector("#review-view");
const exportView = document.querySelector("#export-view");
const paperNav = document.querySelector("#paper-nav");
const importNav = document.querySelector("#import-nav");
const dataNav = document.querySelector("#data-nav");
const qualityNav = document.querySelector("#quality-nav");
const reviewNav = document.querySelector("#review-nav");
const exportNav = document.querySelector("#export-nav");

const viewElements = {
  bank: bankView,
  paper: paperView,
  import: importView,
  editor: editorForm,
  data: dataView,
  quality: qualityView,
  review: reviewView,
  export: exportView,
};

const viewNavigation = {
  bank: bankNav,
  paper: paperNav,
  import: importNav,
  editor: editorNav,
  data: dataNav,
  quality: qualityNav,
  review: reviewNav,
  export: exportNav,
};

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
  return globalThis.dqFormula.flattenContent(content);
}

function hasStructuredBlocks(content) {
  return Boolean(content?.blocks?.some((block) => !["text", "line_break"].includes(block.type)));
}

const { mathDelimiterAt, findClosingDelimiter } = globalThis.dqFormula;

function appendPlainText(container, text) {
  if (text) container.append(document.createTextNode(text.replaceAll("\\$", "$")));
}

function renderMathElement(element, latex, displayMode = false, fallback = "") {
  element.classList.add("content-math");
  if (displayMode) element.classList.add("display");
  if (globalThis.katex) {
    try {
      globalThis.katex.render(latex, element, {
        displayMode,
        output: "htmlAndMathml",
        strict: "warn",
        throwOnError: true,
        trust: false,
      });
      return;
    } catch (error) {
      element.classList.add("math-fallback");
      element.title = "Formula could not be rendered.";
    }
  }
  element.textContent = fallback || (displayMode ? `\\[${latex}\\]` : `\\(${latex}\\)`);
}

function renderTextWithMath(container, value, annotate = false) {
  const text = String(value ?? "");
  let plainStart = 0;
  let cursor = 0;
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
    appendPlainText(container, text.slice(plainStart, cursor));
    const math = document.createElement("span");
    const source = text.slice(cursor, closing + delimiter.length);
    renderMathElement(math, text.slice(latexStart, closing), delimiter === "$$", source);
    if (annotate) {
      math.classList.add("formula-block");
      math.dataset.formulaStart = String(cursor);
      math.dataset.formulaEnd = String(closing + delimiter.length);
      math.setAttribute("role", "button");
      math.setAttribute("tabindex", "0");
      math.setAttribute("aria-label", delimiter === "$$" ? "Edit display formula" : "Edit inline formula");
      math.title = "Edit formula";
    }
    container.append(math);
    cursor = closing + delimiter.length;
    plainStart = cursor;
  }
  appendPlainText(container, text.slice(plainStart));
}

function parseEditableContent(value, language = "en") {
  return globalThis.dqFormula.parseEditableBlocks(value, language);
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
      renderTextWithMath(cell, value);
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
      if (block.type === "math") {
        renderMathElement(element, block.latex || "", Boolean(block.metadata?.display));
      } else if (block.type === "text") {
        renderTextWithMath(element, block.text || "");
      } else {
        element.textContent = block.text || block.alt_text || "";
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

function choiceAnswerValues(answer) {
  if (!answer) return [];
  const values = Array.isArray(answer.value) ? answer.value : [answer.value];
  return values.filter((value) => value !== undefined && value !== null && String(value).trim())
    .map((value) => String(value));
}

function choiceRows(card) {
  return [...card.querySelectorAll(".choice-row")];
}

function makeChoiceRow(choice = {}, language = "en") {
  const row = document.createElement("div");
  row.className = "choice-row";
  row.dataset.original = JSON.stringify(choice);
  const id = document.createElement("input");
  id.className = "choice-id";
  id.required = true;
  id.value = choice.id || "";
  id.setAttribute("aria-label", "Choice id");
  id.title = "Stable choice id";
  const content = document.createElement("textarea");
  content.className = "choice-content";
  content.required = true;
  content.rows = 2;
  content.value = contentText(choice.content);
  content.setAttribute("aria-label", `Choice ${choice.id || "option"} content`);
  const formula = document.createElement("button");
  formula.className = "icon-button choice-formula-insert";
  formula.type = "button";
  formula.title = "Insert formula";
  formula.setAttribute("aria-label", "Insert formula");
  formula.textContent = "fx";
  const remove = document.createElement("button");
  remove.className = "icon-button remove-choice";
  remove.type = "button";
  remove.title = "Remove choice";
  remove.setAttribute("aria-label", "Remove choice");
  remove.textContent = "×";
  row.append(id, content, formula, remove);
  return row;
}

function refreshChoiceAnswerControls(card, selectedValues = null) {
  const type = card.querySelector(".question-type").value;
  const rows = choiceRows(card);
  const ids = rows.map((row) => row.querySelector(".choice-id").value.trim()).filter(Boolean);
  const current = selectedValues || [...card.querySelectorAll(".choice-answer:checked")].map((input) => input.value);
  const single = card.querySelector(".single-answer-control");
  const multiple = card.querySelector(".multiple-answer-control");
  const list = card.querySelector(".answer-choice-list");
  const select = card.querySelector(".question-choice-answer");
  const isSingle = type === "single_choice";
  const isMultiple = type === "multiple_choice";
  single.hidden = !isSingle;
  multiple.hidden = !isMultiple;
  if (!isSingle && !isMultiple) return;
  if (isSingle) {
    select.replaceChildren();
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "Select an answer";
    select.append(empty);
    ids.forEach((id) => {
      const option = document.createElement("option");
      option.value = id;
      option.textContent = id;
      option.selected = current.includes(id);
      select.append(option);
    });
  } else {
    list.replaceChildren();
    ids.forEach((id) => {
      const label = document.createElement("label");
      label.className = "answer-choice-item";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.className = "choice-answer";
      checkbox.value = id;
      checkbox.checked = current.includes(id);
      label.append(checkbox, document.createTextNode(id));
      list.append(label);
    });
  }
}

function renderChoiceEditor(card, question) {
  const list = card.querySelector(".choice-list");
  const choices = question.choices || [];
  list.replaceChildren(...choices.map((choice) => makeChoiceRow(choice, question.language || "en")));
  card.querySelector(".field-empty").hidden = choices.length > 0;
  refreshChoiceAnswerControls(card, choiceAnswerValues(question.answer));
}

function editorValidationIssues(payload) {
  const issues = [];
  for (const [questionIndex, question] of (payload.questions || []).entries()) {
    const path = `Question ${questionIndex + 1}`;
    const choices = question.choices || [];
    const ids = choices.map((choice) => choice.id).filter(Boolean);
    if (["single_choice", "multiple_choice"].includes(question.type)) {
      if (choices.length < 2) issues.push(`${path} needs at least two choices.`);
      if (new Set(ids).size !== ids.length) issues.push(`${path} has duplicate choice ids.`);
      if (choices.some((choice) => !choice.id || !contentText(choice.content).trim())) {
        issues.push(`${path} has a choice with a missing id or content.`);
      }
      const answers = choiceAnswerValues(question.answer);
      if (question.type === "single_choice" && answers.length > 1) issues.push(`${path} needs one correct choice.`);
      if (question.type === "multiple_choice" && answers.length < 1) issues.push(`${path} needs at least one correct choice.`);
      if (answers.some((answer) => !ids.includes(answer))) issues.push(`${path} answer references an unknown choice.`);
    }
  }
  return issues;
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
  for (const [name, element] of Object.entries(viewElements)) element.hidden = name !== view;
  for (const [name, navigation] of Object.entries(viewNavigation)) {
    navigation.classList.toggle("active", name === view);
  }
  if (view === "paper") renderPaperCenter();
  else if (view === "import") renderImportCenter();
  else if (view === "data") renderBankData();
  else if (view === "quality") renderQualityCenter();
  else if (view === "review") renderReviewCenter();
  else if (view === "export") renderExportCenter();
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
      renderTextWithMath(value, answer);
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
  const paper = document.createElement("button");
  paper.className = "expand-btn";
  paper.type = "button";
  const inPaper = state.paperQuestionIds.includes(question.id);
  paper.textContent = inPaper ? "In paper" : "Add to paper";
  paper.disabled = inPaper;
  paper.addEventListener("click", () => addQuestionToPaper(question.id));
  actions.append(paper);
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

function allQuestions(questions = state.current?.questions || []) {
  const result = [];
  for (const question of questions) {
    result.push(question);
    result.push(...allQuestions(question.subquestions || []));
  }
  return result;
}

function downloadJson(payload, filename) {
  const blob = new Blob([`${JSON.stringify(payload, null, 2)}\n`], { type: "application/json" });
  const link = Object.assign(document.createElement("a"), {
    href: URL.createObjectURL(blob),
    download: filename,
  });
  link.click();
  URL.revokeObjectURL(link.href);
}

function createWorkRow(question, actionLabel, action) {
  const row = document.createElement("article");
  row.className = "work-row";
  const copy = document.createElement("div");
  const title = document.createElement("strong");
  title.textContent = question.id;
  const summary = document.createElement("p");
  summary.textContent = stemText(question) || "Empty stem";
  const meta = document.createElement("span");
  meta.textContent = [question.subject, formatType(question.type)].filter(Boolean).join(" · ");
  copy.append(title, summary, meta);
  const button = document.createElement("button");
  button.className = "action-btn secondary compact-action";
  button.type = "button";
  button.textContent = actionLabel;
  button.addEventListener("click", action);
  row.append(copy, button);
  return row;
}

function addQuestionToPaper(questionId) {
  if (!state.current || state.paperQuestionIds.includes(questionId)) return;
  state.paperQuestionIds.push(questionId);
  renderQuestionResults();
  renderPaperCenter();
  setStatus(`${questionId} added to the paper draft.`);
}

function movePaperQuestion(index, offset) {
  const target = index + offset;
  if (target < 0 || target >= state.paperQuestionIds.length) return;
  [state.paperQuestionIds[index], state.paperQuestionIds[target]] = [
    state.paperQuestionIds[target],
    state.paperQuestionIds[index],
  ];
  renderPaperCenter();
}

function removePaperQuestion(questionId) {
  state.paperQuestionIds = state.paperQuestionIds.filter((id) => id !== questionId);
  renderQuestionResults();
  renderPaperCenter();
}

function renderPaperCenter() {
  const sourceList = document.querySelector("#paper-source-list");
  const draftList = document.querySelector("#paper-draft-list");
  sourceList.replaceChildren();
  draftList.replaceChildren();
  if (!state.current) return;
  const questions = state.current.questions || [];
  document.querySelector("#paper-source-title").textContent = state.current.title;
  document.querySelector("#paper-count").textContent = `${state.paperQuestionIds.length} question${state.paperQuestionIds.length === 1 ? "" : "s"}`;
  for (const question of questions) {
    const selected = state.paperQuestionIds.includes(question.id);
    const row = createWorkRow(question, selected ? "Added" : "Add", () => addQuestionToPaper(question.id));
    row.querySelector("button").disabled = selected;
    sourceList.append(row);
  }
  const byId = new Map(questions.map((question) => [question.id, question]));
  state.paperQuestionIds.forEach((questionId, index) => {
    const question = byId.get(questionId);
    if (!question) return;
    const row = createWorkRow(question, "Remove", () => removePaperQuestion(questionId));
    const controls = document.createElement("div");
    controls.className = "row-controls";
    for (const [label, title, offset] of [["\u2191", "Move up", -1], ["\u2193", "Move down", 1]]) {
      const button = document.createElement("button");
      button.className = "icon-control";
      button.type = "button";
      button.textContent = label;
      button.title = title;
      button.setAttribute("aria-label", title);
      button.disabled = offset < 0 ? index === 0 : index === state.paperQuestionIds.length - 1;
      button.addEventListener("click", () => movePaperQuestion(index, offset));
      controls.append(button);
    }
    controls.append(row.lastElementChild);
    row.append(controls);
    draftList.append(row);
  });
  if (!questions.length) appendEmptyState(sourceList, "The collection has no questions.");
  if (!state.paperQuestionIds.length) appendEmptyState(draftList, "Add questions from the pool to build a paper.");
}

function paperPayload() {
  const questions = state.current?.questions || [];
  const byId = new Map(questions.map((question) => [question.id, question]));
  const title = document.querySelector("#paper-title").value.trim() || "Untitled paper";
  return {
    schema_version: "1.0",
    id: `paper-${state.current.id}`,
    title,
    description: `Paper assembled from ${state.current.title}.`,
    language: state.current.language,
    questions: state.paperQuestionIds.map((id) => structuredClone(byId.get(id))).filter(Boolean),
    metadata: { "org.dqquestionbank.paper": { source_set_id: state.current.id } },
  };
}

function appendDefinition(list, term, value) {
  const wrapper = document.createElement("div");
  const label = document.createElement("dt");
  label.textContent = term;
  const detail = document.createElement("dd");
  detail.textContent = value;
  wrapper.append(label, detail);
  list.append(wrapper);
}

function renderImportCenter() {
  const result = document.querySelector("#import-result");
  const note = document.querySelector("#import-result-note");
  const review = document.querySelector("#review-import");
  result.replaceChildren();
  if (!state.importSummary) {
    note.textContent = "No import has been processed in this session.";
    review.disabled = !state.current;
    return;
  }
  note.textContent = state.importSummary.message;
  appendDefinition(result, "Source", state.importSummary.source);
  appendDefinition(result, "Collection", state.importSummary.title);
  appendDefinition(result, "Questions", String(state.importSummary.questionCount));
  appendDefinition(result, "Schema", state.importSummary.schemaVersion);
  review.disabled = false;
}

function appendMetric(container, label, value, detail) {
  const metric = document.createElement("div");
  metric.className = "metric-item";
  const name = document.createElement("span");
  name.textContent = label;
  const count = document.createElement("strong");
  count.textContent = String(value);
  const note = document.createElement("small");
  note.textContent = detail;
  metric.append(name, count, note);
  container.append(metric);
}

function renderBankData() {
  const metrics = document.querySelector("#data-metrics");
  const coverage = document.querySelector("#data-coverage-body");
  const collections = document.querySelector("#data-collection-list");
  metrics.replaceChildren();
  coverage.replaceChildren();
  collections.replaceChildren();
  if (!state.current) return;
  const questions = allQuestions();
  const answered = questions.filter((question) => answerText(question.answer)).length;
  const solved = questions.filter((question) => contentText(question.solution)).length;
  const blocks = questions.flatMap((question) => question.stem?.blocks || []);
  appendMetric(metrics, "Questions", questions.length, "including subquestions");
  appendMetric(metrics, "Answered", answered, `${percentage(answered, questions.length)}% coverage`);
  appendMetric(metrics, "Solutions", solved, `${percentage(solved, questions.length)}% coverage`);
  appendMetric(metrics, "Rich blocks", blocks.filter((block) => !["text", "line_break"].includes(block.type)).length, "math, tables, images, and code");
  const subjectGroups = new Map();
  for (const question of questions) {
    const subject = question.subject || "Unassigned";
    if (!subjectGroups.has(subject)) subjectGroups.set(subject, []);
    subjectGroups.get(subject).push(question);
  }
  for (const [subject, items] of [...subjectGroups.entries()].sort(([left], [right]) => left.localeCompare(right))) {
    const row = document.createElement("tr");
    const values = [
      subject,
      items.length,
      items.filter((question) => answerText(question.answer)).length,
      items.filter((question) => contentText(question.solution)).length,
      new Set(items.map((question) => formatType(question.type))).size,
    ];
    for (const value of values) {
      const cell = document.createElement("td");
      cell.textContent = String(value);
      row.append(cell);
    }
    coverage.append(row);
  }
  for (const item of state.sets) {
    const row = document.createElement("button");
    row.className = `inventory-row${item.id === state.current.id ? " active" : ""}`;
    row.type = "button";
    const title = document.createElement("strong");
    title.textContent = item.title;
    const detail = document.createElement("span");
    detail.textContent = `${item.question_count} questions`;
    row.append(title, detail);
    row.addEventListener("click", () => loadSet(item.id));
    collections.append(row);
  }
}

function percentage(value, total) {
  return total ? Math.round((value / total) * 100) : 0;
}

function inspectDelimitedMath(value) {
  const text = String(value || "");
  const expressions = [];
  let cursor = 0;
  while (cursor < text.length) {
    const delimiter = mathDelimiterAt(text, cursor);
    if (!delimiter) {
      cursor += 1;
      continue;
    }
    const start = cursor + delimiter.length;
    const closing = findClosingDelimiter(text, start, delimiter);
    if (closing < 0) return { expressions, unclosed: true };
    expressions.push({ latex: text.slice(start, closing), display: delimiter === "$$" });
    cursor = closing + delimiter.length;
  }
  return { expressions, unclosed: false };
}

function addMathFindings(findings, question, questionIndex, field, value, explicit = false) {
  const inspected = explicit
    ? { expressions: [{ latex: String(value || ""), display: false }], unclosed: false }
    : inspectDelimitedMath(value);
  if (inspected.unclosed) {
    findings.push(makeFinding("error", question, questionIndex, field, "Unclosed math delimiter."));
  }
  for (const expression of inspected.expressions) {
    if (!expression.latex.trim()) {
      findings.push(makeFinding("error", question, questionIndex, field, "Empty math expression."));
      continue;
    }
    try {
      globalThis.katex?.renderToString(expression.latex, {
        displayMode: expression.display,
        strict: "warn",
        throwOnError: true,
        trust: false,
      });
    } catch (error) {
      findings.push(makeFinding("error", question, questionIndex, field, "KaTeX cannot render this expression."));
    }
  }
}

function inspectContentMath(findings, question, questionIndex, field, content) {
  for (const block of content?.blocks || []) {
    if (block.type === "math") addMathFindings(findings, question, questionIndex, field, block.latex, true);
    else if (block.type === "text") addMathFindings(findings, question, questionIndex, field, block.text);
    else if (block.type === "table") {
      for (const row of block.rows || []) {
        for (const cell of row) addMathFindings(findings, question, questionIndex, field, cell);
      }
    }
  }
}

function makeFinding(severity, question, questionIndex, field, message) {
  return { severity, questionId: question.id, questionIndex, field, message };
}

function runQualityChecks() {
  const findings = [];
  const seen = new Set();
  const payload = state.view === "editor" ? collectPayload() : state.current;
  for (const [questionIndex, question] of (payload?.questions || []).entries()) {
    if (seen.has(question.id)) findings.push(makeFinding("error", question, questionIndex, "metadata", "Duplicate question ID."));
    seen.add(question.id);
    if (!stemText(question).trim()) findings.push(makeFinding("error", question, questionIndex, "stem", "Question stem is empty."));
    if (!question.subject) findings.push(makeFinding("warning", question, questionIndex, "metadata", "Subject is not assigned."));
    if (!answerText(question.answer)) findings.push(makeFinding("warning", question, questionIndex, "answer", "Answer is missing."));
    if (!contentText(question.solution)) findings.push(makeFinding("warning", question, questionIndex, "solution", "Solution is missing."));
    for (const issue of editorValidationIssues({ questions: [question] })) {
      findings.push(makeFinding("error", question, questionIndex, issue.includes("choice") ? "choices" : "answer", issue.replace(/^Question 1 /, "")));
    }
    inspectContentMath(findings, question, questionIndex, "stem", question.stem);
    for (const choice of question.choices || []) inspectContentMath(findings, question, questionIndex, "choices", choice.content);
    inspectContentMath(findings, question, questionIndex, "solution", question.solution);
    addMathFindings(findings, question, questionIndex, "answer", answerText(question.answer));
  }
  state.qualityFindings = findings;
  state.qualityHasRun = true;
  renderQualityCenter();
  updateEditorAudit();
  setStatus(`Quality checks completed with ${findings.length} finding${findings.length === 1 ? "" : "s"}.`);
}

function updateEditorAudit() {
  const count = document.querySelector("#editor-quality-count");
  const summary = document.querySelector("#editor-quality-summary");
  const qualityState = document.querySelector("#editor-quality-state");
  if (!count || !summary || !qualityState) return;
  if (!state.qualityHasRun) {
    count.textContent = "-";
    summary.textContent = "Checks have not run.";
    qualityState.textContent = "Waiting for a local check";
    qualityState.classList.remove("warning");
    return;
  }
  count.textContent = String(state.qualityFindings.length);
  summary.textContent = state.qualityFindings.length
    ? `${new Set(state.qualityFindings.map((finding) => finding.questionId)).size} questions need attention`
    : "Current local checks passed";
  qualityState.textContent = state.qualityFindings.length
    ? "Review findings before saving"
    : "Latest deterministic check passed";
  qualityState.classList.toggle("warning", Boolean(state.qualityFindings.length));
}

function setEditorDirty(dirty) {
  state.editorDirty = dirty;
  const saveState = document.querySelector("#editor-save-state");
  if (!saveState) return;
  saveState.classList.toggle("unsaved", dirty);
  saveState.lastChild.textContent = dirty ? " Unsaved" : " Saved";
}

function discardEditorChanges(message = "Unsaved editor changes were discarded.") {
  if (state.view !== "editor" || !state.editorDirty) return false;
  populateEditor(state.current);
  setStatus(message);
  return true;
}

function setSaveInFlight(inFlight) {
  state.saveInFlight = inFlight;
  const button = editorForm.querySelector('button[type="submit"]');
  if (!button) return;
  button.disabled = inFlight;
  button.setAttribute("aria-busy", String(inFlight));
  button.textContent = inFlight ? "Saving..." : "Save changes";
  if (inFlight) setStatus("Saving changes locally...");
}

function renderEditorTextPreview(container, value) {
  container.replaceChildren();
  if (String(value || "").trim()) renderTextWithMath(container, value, true);
}

const formulaDialog = document.querySelector("#formula-dialog");
const formulaModeControl = document.querySelector("#formula-mode");
const formulaSourceInput = document.querySelector("#formula-source");
const formulaPreviewPane = document.querySelector("#formula-preview");
const formulaErrorLine = document.querySelector("#formula-error");
const formulaApplyButton = document.querySelector("#formula-apply");
const formulaDialogTitle = document.querySelector("#formula-dialog-title");
let formulaTarget = null;

function updateFormulaPreview() {
  const latex = formulaSourceInput.value;
  const display = formulaModeControl.value === "display";
  formulaPreviewPane.replaceChildren();
  formulaErrorLine.replaceChildren();
  formulaDialog.classList.remove("has-error");
  if (!latex.trim()) {
    const hint = document.createElement("p");
    hint.className = "formula-hint";
    hint.textContent = "Type LaTeX source to preview the formula.";
    formulaPreviewPane.append(hint);
    return;
  }
  if (globalThis.katex) {
    try {
      const holder = document.createElement("span");
      globalThis.katex.render(latex, holder, {
        displayMode: display,
        output: "htmlAndMathml",
        strict: "warn",
        throwOnError: true,
        trust: false,
      });
      formulaPreviewPane.append(holder);
      return;
    } catch (error) {
      // Fall through to the reviewable error state below.
    }
  }
  formulaDialog.classList.add("has-error");
  const raw = document.createElement("code");
  raw.className = "formula-raw-source";
  raw.textContent = latex;
  formulaPreviewPane.append(raw);
  const message = document.createElement("span");
  message.textContent = "KaTeX cannot render this formula yet. The LaTeX source stays visible and is never erased.";
  formulaErrorLine.append(message);
}

function openFormulaEditor(textarea, range = null) {
  let target = range;
  if (!target) {
    const caret = textarea.selectionStart ?? textarea.value.length;
    target = dqFormula.findFormulaRange(textarea.value, caret);
  }
  formulaTarget = { textarea, range: target };
  formulaModeControl.value = target?.display ? "display" : "inline";
  formulaSourceInput.value = target ? target.latex : "";
  formulaApplyButton.textContent = target ? "Update formula" : "Insert formula";
  formulaDialogTitle.textContent = target ? "Edit formula block" : "Insert formula block";
  updateFormulaPreview();
  formulaDialog.showModal();
  formulaSourceInput.focus();
  formulaSourceInput.select();
}

function applyFormulaEdit() {
  if (!formulaTarget) return;
  const { textarea, range } = formulaTarget;
  const latex = formulaSourceInput.value.trim();
  if (!latex) {
    formulaErrorLine.replaceChildren();
    const message = document.createElement("span");
    message.textContent = "Enter the LaTeX source before applying.";
    formulaErrorLine.append(message);
    formulaSourceInput.focus();
    return;
  }
  const display = formulaModeControl.value === "display";
  const caret = textarea.selectionStart ?? textarea.value.length;
  const result = range
    ? dqFormula.replaceRange(textarea.value, range.start, range.end, latex, display)
    : dqFormula.insertFormula(textarea.value, caret, latex, display);
  textarea.value = result.text;
  textarea.focus();
  textarea.setSelectionRange(result.start, result.end);
  textarea.dispatchEvent(new Event("input", { bubbles: true }));
  formulaTarget = null;
  formulaDialog.close();
}

function renderQualityCenter() {
  const metrics = document.querySelector("#quality-metrics");
  const queue = document.querySelector("#quality-findings");
  metrics.replaceChildren();
  queue.replaceChildren();
  const errors = state.qualityFindings.filter((finding) => finding.severity === "error");
  const warnings = state.qualityFindings.filter((finding) => finding.severity === "warning");
  const affected = new Set(state.qualityFindings.map((finding) => finding.questionId)).size;
  appendMetric(metrics, "Errors", errors.length, "rendering or structural blockers");
  appendMetric(metrics, "Warnings", warnings.length, "fields requiring review");
  appendMetric(metrics, "Affected", affected, "unique questions");
  appendMetric(metrics, "Checked", state.current?.questions?.length || 0, "questions in this collection");
  document.querySelector("#quality-all-count").textContent = String(state.qualityFindings.length);
  document.querySelector("#quality-error-count").textContent = String(errors.length);
  document.querySelector("#quality-warning-count").textContent = String(warnings.length);
  const visible = state.qualityFindings.filter((finding) => state.qualityFilter === "all" || finding.severity === state.qualityFilter);
  document.querySelector("#quality-note").textContent = !state.qualityHasRun
    ? "Run checks to build the queue."
    : state.qualityFindings.length
      ? `${visible.length} of ${state.qualityFindings.length} findings shown.`
      : "All deterministic checks passed.";
  for (const finding of visible) {
    const item = document.createElement("article");
    item.className = `quality-finding ${finding.severity}`;
    const copy = document.createElement("div");
    const heading = document.createElement("strong");
    heading.textContent = `${finding.questionId} · ${finding.field}`;
    const message = document.createElement("p");
    message.textContent = finding.message;
    copy.append(heading, message);
    const action = document.createElement("button");
    action.className = "action-btn secondary compact-action";
    action.type = "button";
    action.textContent = "Open in Editor";
    action.addEventListener("click", () => openQualityFinding(finding));
    item.append(copy, action);
    queue.append(item);
  }
  if (!visible.length) {
    appendEmptyState(
      queue,
      state.qualityHasRun ? "No findings match this filter." : "No checks have run yet.",
    );
  }
}

function appendEmptyState(container, message) {
  const empty = document.createElement("p");
  empty.className = "work-empty";
  empty.textContent = message;
  container.append(empty);
}

function openQualityFinding(finding) {
  state.selectedQuestionIndex = finding.questionIndex;
  setView("editor");
  updateEditorSelection();
  const card = document.querySelector(".edit-question-card:not([hidden])");
  const target = finding.field === "metadata" ? card : card?.querySelector(`[data-editor-section="${finding.field}"]`);
  target?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function toggleQuestionReviewed(questionId) {
  state.reviewedQuestionIds = state.reviewedQuestionIds.includes(questionId)
    ? state.reviewedQuestionIds.filter((id) => id !== questionId)
    : [...state.reviewedQuestionIds, questionId];
  renderReviewCenter();
}

function openQuestionInEditor(index) {
  state.selectedQuestionIndex = index;
  setView("editor");
  updateEditorSelection();
}

function renderReviewCenter() {
  const metrics = document.querySelector("#review-metrics");
  const list = document.querySelector("#review-question-list");
  metrics.replaceChildren();
  list.replaceChildren();
  if (!state.current) return;
  const questions = state.current.questions || [];
  const reviewed = questions.filter((question) => state.reviewedQuestionIds.includes(question.id));
  const answered = questions.filter((question) => answerText(question.answer));
  appendMetric(metrics, "Questions", questions.length, "active collection");
  appendMetric(metrics, "Reviewed", reviewed.length, `${percentage(reviewed.length, questions.length)}% complete`);
  appendMetric(metrics, "Remaining", questions.length - reviewed.length, "session checklist");
  appendMetric(metrics, "Answered", answered.length, `${percentage(answered.length, questions.length)}% coverage`);
  questions.forEach((question, index) => {
    const row = createWorkRow(
      question,
      state.reviewedQuestionIds.includes(question.id) ? "Reviewed" : "Mark reviewed",
      () => toggleQuestionReviewed(question.id),
    );
    const controls = document.createElement("div");
    controls.className = "row-controls";
    const edit = document.createElement("button");
    edit.className = "action-btn secondary compact-action";
    edit.type = "button";
    edit.textContent = "Open in Editor";
    edit.addEventListener("click", () => openQuestionInEditor(index));
    controls.append(edit, row.lastElementChild);
    row.append(controls);
    if (state.reviewedQuestionIds.includes(question.id)) row.classList.add("reviewed");
    list.append(row);
  });
}

function renderExportCenter() {
  if (!state.current) return;
  document.querySelector("#export-set-detail").textContent = `${state.current.questions.length} questions · schema ${state.current.schema_version}`;
  document.querySelector("#export-paper-detail").textContent = `${state.paperQuestionIds.length} question${state.paperQuestionIds.length === 1 ? "" : "s"} selected`;
  document.querySelector("#export-center-paper").disabled = !state.paperQuestionIds.length;
}

function exportPaperDraft() {
  if (!state.current || !state.paperQuestionIds.length) {
    setStatus("Add at least one question before exporting a paper.", true);
    return;
  }
  const payload = paperPayload();
  downloadJson(payload, `${payload.id}.json`);
  setStatus("Paper draft exported as canonical JSON.");
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
  fragment.querySelector(".question-editor-summary").textContent = [
    question.subject,
    formatType(question.type),
    question.metadata?.grade,
  ].filter(Boolean).join(" · ");
  fragment.querySelector(".question-source").textContent = question.source?.title || "Not provided";
  fragment.querySelector(".question-id").value = question.id || "";
  fragment.querySelector(".question-type").value = question.type || "short_answer";
  fragment.querySelector(".question-language").value = question.language || "en";
  fragment.querySelector(".question-subject").value = question.subject || "";
  fragment.querySelector(".question-grade").value = question.metadata?.grade || "";
  fragment.querySelector(".question-category").value = question.metadata?.question_category || "";
  fragment.querySelector(".question-difficulty").value = question.difficulty ?? "";
  fragment.querySelector(".question-tags").value = (question.tags || []).join(", ");
  fragment.querySelector(".question-source-title").value = question.source?.title || "";
  fragment.querySelector(".question-source-year").value = question.source?.year ?? "";
  fragment.querySelector(".question-stem").value = stemText(question);
  const stemPreview = fragment.querySelector(".stem-preview");
  stemPreview.hidden = false;
  if (hasStructuredBlocks(question.stem)) {
    renderStructuredContent(stemPreview, question.stem);
  } else {
    renderEditorTextPreview(stemPreview, stemText(question));
  }
  renderChoiceEditor(card, question);
  const answer = answerText(question.answer);
  fragment.querySelector(".question-answer").value = answer;
  renderEditorTextPreview(fragment.querySelector(".answer-preview"), answer);
  fragment.querySelector(".question-analysis").value = question.metadata?.analysis || "";
  renderEditorTextPreview(
    fragment.querySelector(".analysis-preview"),
    question.metadata?.analysis || "",
  );
  const solution = contentText(question.solution);
  fragment.querySelector(".question-solution").value = solution;
  const solutionPreview = fragment.querySelector(".solution-preview");
  if (hasStructuredBlocks(question.solution)) renderStructuredContent(solutionPreview, question.solution);
  else renderEditorTextPreview(solutionPreview, solution);
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
  const question = state.current?.questions?.[state.selectedQuestionIndex];
  document.querySelector("#editor-context-id").textContent = question?.id || "Not loaded";
  document.querySelector("#editor-context-source").textContent = question?.source?.title || "Not provided";
  setActiveEditorField("stem");
}

function setActiveEditorField(field) {
  for (const button of document.querySelectorAll("#editor-field-nav [data-editor-field]")) {
    const active = button.dataset.editorField === field;
    button.classList.toggle("active", active);
    if (active) button.setAttribute("aria-current", "true");
    else button.removeAttribute("aria-current");
  }
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
  setEditorDirty(false);
  updateEditorAudit();
}

function renderWorkspace(payload, persisted = true, view = "bank") {
  const collectionChanged = state.selectedId !== payload.id;
  state.current = payload;
  state.selectedId = payload.id;
  state.selectedQuestionIndex = Math.min(state.selectedQuestionIndex, Math.max(payload.questions.length - 1, 0));
  state.persisted = persisted;
  state.subject = "";
  state.type = "";
  state.qualityFindings = [];
  state.qualityHasRun = false;
  if (collectionChanged) {
    state.paperQuestionIds = [];
    state.reviewedQuestionIds = [];
  }
  for (const navigation of [paperNav, editorNav, dataNav, qualityNav]) navigation.disabled = false;
  document.querySelector("#review-nav").disabled = false;
  document.querySelector("#export-nav").disabled = false;
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
    question.metadata = { ...(question.metadata || {}) };
    const grade = card.querySelector(".question-grade").value.trim();
    const category = card.querySelector(".question-category").value.trim();
    if (grade) question.metadata.grade = grade;
    else delete question.metadata.grade;
    if (category) question.metadata.question_category = category;
    else delete question.metadata.question_category;
    const difficulty = card.querySelector(".question-difficulty").value.trim();
    if (difficulty) question.difficulty = Number(difficulty);
    else delete question.difficulty;
    const tags = card.querySelector(".question-tags").value.split(",").map((tag) => tag.trim()).filter(Boolean);
    question.tags = [...new Set(tags)];
    const sourceTitle = card.querySelector(".question-source-title").value.trim();
    const sourceYear = card.querySelector(".question-source-year").value.trim();
    question.source = { ...(question.source || {}) };
    if (sourceTitle) question.source.title = sourceTitle;
    else delete question.source.title;
    if (sourceYear) question.source.year = Number(sourceYear);
    else delete question.source.year;
    if (!Object.keys(question.source).length) delete question.source;
    const editedStem = card.querySelector(".question-stem").value;
    if (editedStem !== card.dataset.originalStem) {
      question.stem = parseEditableContent(editedStem, question.language);
    }
    const rows = choiceRows(card);
    if (rows.length || question.choices?.length) {
      question.choices = rows.map((row) => {
        const original = JSON.parse(row.dataset.original || "{}");
        const editedContent = row.querySelector(".choice-content").value;
        const originalContent = contentText(original.content);
        return {
          ...original,
          id: row.querySelector(".choice-id").value.trim(),
          content: editedContent === originalContent
            ? original.content
            : parseEditableContent(editedContent, question.language),
        };
      });
    }
    if (["single_choice", "multiple_choice"].includes(question.type)) {
      const selected = question.type === "single_choice"
        ? [card.querySelector(".question-choice-answer").value].filter(Boolean)
        : [...card.querySelectorAll(".choice-answer:checked")].map((input) => input.value);
      if (selected.length) {
        question.answer = {
          ...(question.answer || {}),
          kind: question.type === "multiple_choice" ? "choices" : "choice",
          value: question.type === "multiple_choice" ? selected : selected[0],
        };
      } else {
        delete question.answer;
      }
    } else {
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
    }
    const editedAnalysis = card.querySelector(".question-analysis").value;
    if (editedAnalysis !== card.dataset.originalAnalysis) {
      if (editedAnalysis) question.metadata.analysis = editedAnalysis;
      else delete question.metadata.analysis;
    }
    const editedSolution = card.querySelector(".question-solution").value;
    if (editedSolution !== card.dataset.originalSolution) {
      if (editedSolution) question.solution = parseEditableContent(editedSolution, question.language);
      else delete question.solution;
    }
    if (!Object.keys(question.metadata).length) delete question.metadata;
    return question;
  });
  return payload;
}

function editCurrentQuestion() {
  setView("editor");
  updateEditorSelection();
  runQualityChecks();
  editorForm.scrollIntoView({ behavior: "smooth", block: "start" });
}

function exportCurrentSet() {
  if (!state.current) return;
  const payload = state.view === "editor" ? collectPayload() : state.current;
  downloadJson(payload, `${payload.id || "question-set"}.json`);
}

async function loadDatabaseCase() {
  loadCaseButton.disabled = true;
  document.querySelector("#empty-load-case").disabled = true;
  try {
    const payload = await request("/api/case/load", { method: "POST" });
    const targetView = state.view === "import" ? "import" : "bank";
    renderWorkspace(payload, true, targetView);
    await refreshList(payload.id);
    state.importSummary = {
      source: "Bundled public SQLite case",
      title: payload.title,
      questionCount: payload.questions.length,
      schemaVersion: payload.schema_version,
      message: "The reviewed public case passed adapter and schema validation.",
    };
    if (targetView === "import") renderImportCenter();
    caseLoadError.hidden = true;
    setStatus("Public database case loaded into the question bank.");
  } catch (error) {
    caseLoadError.textContent = `Could not load the public case (${error.message}). Choose "Open public case" to try again.`;
    caseLoadError.hidden = false;
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
  if (state.saveInFlight) return;
  setSaveInFlight(true);
  try {
    const payload = collectPayload();
    const editorIssues = editorValidationIssues(payload);
    if (editorIssues.length) {
      runQualityChecks();
      throw new Error(`Resolve editor validation issues before saving: ${editorIssues[0]}`);
    }
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
  } finally {
    setSaveInFlight(false);
  }
});
document.querySelector("#import-file").addEventListener("change", async (event) => {
  const [file] = event.target.files;
  if (!file) return;
  try {
    const payload = JSON.parse(await file.text());
    const targetView = state.view === "import" ? "import" : "bank";
    const saved = await request("/api/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    renderWorkspace(saved, true, targetView);
    await refreshList(saved.id);
    state.importSummary = {
      source: file.name,
      title: saved.title,
      questionCount: saved.questions.length,
      schemaVersion: saved.schema_version,
      message: "Canonical JSON passed schema and semantic validation and was saved locally.",
    };
    if (targetView === "import") renderImportCenter();
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
  discardEditorChanges();
  setView("bank");
  setStatus("Unsaved editor changes were discarded.");
});
bankNav.addEventListener("click", () => {
  if (state.current) {
    discardEditorChanges();
    setView("bank");
  }
});
paperNav.addEventListener("click", () => {
  if (state.current) {
    discardEditorChanges();
    setView("paper");
  }
});
importNav.addEventListener("click", () => {
  discardEditorChanges();
  setView("import");
});
editorNav.addEventListener("click", () => {
  if (state.current) {
    setView("editor");
    updateEditorSelection();
    runQualityChecks();
  }
});
dataNav.addEventListener("click", () => {
  if (state.current) {
    discardEditorChanges();
    setView("data");
  }
});
qualityNav.addEventListener("click", () => {
  if (state.current) {
    discardEditorChanges();
    setView("quality");
    runQualityChecks();
  }
});
reviewNav.addEventListener("click", () => {
  if (state.current) {
    discardEditorChanges();
    setView("review");
  }
  setMoreMenu(false);
});
exportNav.addEventListener("click", () => {
  if (state.current) {
    discardEditorChanges();
    setView("export");
  }
  setMoreMenu(false);
});
document.querySelector("#import-load-case").addEventListener("click", loadDatabaseCase);
document.querySelector("#review-import").addEventListener("click", () => {
  if (state.current) setView("bank");
});
document.querySelector("#add-all-to-paper").addEventListener("click", () => {
  if (!state.current) return;
  state.paperQuestionIds = state.current.questions.map((question) => question.id);
  renderQuestionResults();
  renderPaperCenter();
});
document.querySelector("#clear-paper").addEventListener("click", () => {
  state.paperQuestionIds = [];
  renderQuestionResults();
  renderPaperCenter();
});
document.querySelector("#export-paper").addEventListener("click", () => {
  exportPaperDraft();
});
document.querySelector("#review-all").addEventListener("click", () => {
  if (!state.current) return;
  state.reviewedQuestionIds = state.current.questions.map((question) => question.id);
  renderReviewCenter();
});
document.querySelector("#review-to-paper").addEventListener("click", () => setView("paper"));
document.querySelector("#export-center-set").addEventListener("click", exportCurrentSet);
document.querySelector("#export-center-paper").addEventListener("click", exportPaperDraft);
document.querySelector("#run-quality").addEventListener("click", runQualityChecks);
document.querySelector("#quality-view").addEventListener("click", (event) => {
  const filter = event.target.closest("[data-quality-filter]");
  if (!filter) return;
  state.qualityFilter = filter.dataset.qualityFilter;
  for (const button of document.querySelectorAll("[data-quality-filter]")) {
    button.classList.toggle("active", button === filter);
  }
  renderQualityCenter();
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
  setActiveEditorField(button.dataset.editorField);
  const card = document.querySelector(".edit-question-card:not([hidden])");
  card?.querySelector(`[data-editor-section="${button.dataset.editorField}"]`)
    ?.scrollIntoView({ behavior: "smooth", block: "start" });
});
editorForm.addEventListener("click", (event) => {
  const addChoice = event.target.closest(".add-choice");
  if (addChoice) {
    const card = addChoice.closest(".edit-question-card");
    const rows = choiceRows(card);
    const nextId = String.fromCharCode(65 + rows.length);
    card.querySelector(".choice-list").append(makeChoiceRow({ id: nextId, content: { blocks: [{ type: "text", text: "", language: card.querySelector(".question-language").value }] } }));
    card.querySelector(".field-empty").hidden = true;
    refreshChoiceAnswerControls(card);
    setEditorDirty(true);
    card.querySelector(".choice-row:last-child .choice-content")?.focus();
    return;
  }
  const removeChoice = event.target.closest(".remove-choice");
  if (removeChoice) {
    const card = removeChoice.closest(".edit-question-card");
    removeChoice.closest(".choice-row")?.remove();
    card.querySelector(".field-empty").hidden = choiceRows(card).length > 0;
    refreshChoiceAnswerControls(card);
    setEditorDirty(true);
    return;
  }
  const insertFormulaButton = event.target.closest(".editor-formula-insert, .choice-formula-insert");
  if (insertFormulaButton) {
    const scope = insertFormulaButton.closest(".choice-row") || insertFormulaButton.closest(".editor-field");
    const textarea = scope?.querySelector("textarea");
    if (textarea) {
      const field = textarea.closest(".editor-field");
      if (field && !field.classList.contains("source-open")) {
        field.classList.add("source-open");
        const fieldToggle = field.querySelector(".editor-source-toggle");
        if (fieldToggle) fieldToggle.textContent = "Show preview";
      }
      openFormulaEditor(textarea, null);
    }
    return;
  }
  const formulaBlock = event.target.closest(".formula-block");
  if (formulaBlock) {
    const field = formulaBlock.closest(".editor-field");
    const textarea = field?.querySelector("textarea");
    if (!textarea) return;
    const token = dqFormula
      .parseDelimitedText(textarea.value)
      .find((item) => item.type === "math" && item.start === Number(formulaBlock.dataset.formulaStart));
    openFormulaEditor(textarea, token || null);
    return;
  }
  const toggle = event.target.closest(".editor-source-toggle");
  if (!toggle) return;
  const field = toggle.closest(".editor-field");
  const open = field.classList.toggle("source-open");
  toggle.textContent = open ? "Show preview" : "Edit source";
  if (open) field.querySelector("textarea")?.focus();
});
editorForm.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" && event.key !== " ") return;
  const formulaBlock = event.target.closest(".formula-block");
  if (!formulaBlock) return;
  event.preventDefault();
  formulaBlock.click();
});
formulaDialog.addEventListener("close", () => {
  formulaTarget = null;
});
document.querySelector("#formula-cancel").addEventListener("click", () => formulaDialog.close());
document.querySelector("#formula-form").addEventListener("submit", (event) => {
  event.preventDefault();
  applyFormulaEdit();
});
formulaSourceInput.addEventListener("input", updateFormulaPreview);
formulaModeControl.addEventListener("change", updateFormulaPreview);
questionList.addEventListener("input", (event) => {
  setEditorDirty(true);
  const card = event.target.closest(".edit-question-card");
  if (event.target.matches(".question-id")) {
    const selectedOption = editorQuestionSelect.options[state.selectedQuestionIndex];
    if (selectedOption) selectedOption.textContent = `${state.selectedQuestionIndex + 1}. ${event.target.value || "Untitled question"}`;
    document.querySelector("#editor-context-id").textContent = event.target.value || "Untitled question";
  } else if (event.target.matches(".question-stem")) {
    renderEditorTextPreview(card.querySelector(".stem-preview"), event.target.value);
  } else if (event.target.matches(".question-answer")) {
    renderEditorTextPreview(card.querySelector(".answer-preview"), event.target.value);
  } else if (event.target.matches(".question-analysis")) {
    renderEditorTextPreview(card.querySelector(".analysis-preview"), event.target.value);
  } else if (event.target.matches(".question-solution")) {
    renderEditorTextPreview(card.querySelector(".solution-preview"), event.target.value);
  } else if (event.target.matches(".choice-id")) {
    refreshChoiceAnswerControls(card);
    card.querySelectorAll(".choice-content").forEach((content) => {
      const id = content.closest(".choice-row")?.querySelector(".choice-id")?.value || "option";
      content.setAttribute("aria-label", `Choice ${id} content`);
    });
  }
});
questionList.addEventListener("change", (event) => {
  if (!event.target.matches(".question-type, .question-choice-answer, .choice-answer")) return;
  const card = event.target.closest(".edit-question-card");
  if (event.target.matches(".question-type")) refreshChoiceAnswerControls(card);
  setEditorDirty(true);
});
editorForm.addEventListener("input", (event) => {
  if (!event.target.closest("#question-list")) setEditorDirty(true);
});
window.addEventListener("beforeunload", (event) => {
  if (!state.editorDirty || state.saveInFlight) return;
  event.preventDefault();
  event.returnValue = "";
});
document.querySelector("#editor-run-quality").addEventListener("click", runQualityChecks);
document.querySelector("#editor-open-quality").addEventListener("click", () => {
  setView("quality");
  runQualityChecks();
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
