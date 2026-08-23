"use strict";

(() => {
  const STORAGE_PREFIX = "dq-questionbank:draft:v1:";
  const AUTOSAVE_DELAY_MS = 400;
  let autosaveTimer = null;

  function storageKey(collectionId) {
    return `${STORAGE_PREFIX}${collectionId}`;
  }

  function readDraft(collectionId) {
    if (!collectionId) return null;
    try {
      const raw = localStorage.getItem(storageKey(collectionId));
      if (!raw) return null;
      const draft = JSON.parse(raw);
      const valid = draft?.version === 1
        && draft.collectionId === collectionId
        && draft.payload
        && Array.isArray(draft.payload.questions);
      if (!valid) {
        localStorage.removeItem(storageKey(collectionId));
        return null;
      }
      return draft;
    } catch (error) {
      try {
        localStorage.removeItem(storageKey(collectionId));
      } catch (storageError) {
        // localStorage may be unavailable; recovery should never break the editor.
      }
      return null;
    }
  }

  function writeDraft(collectionId, payload) {
    if (!collectionId || !payload) return false;
    try {
      localStorage.setItem(storageKey(collectionId), JSON.stringify({
        version: 1,
        collectionId,
        savedAt: new Date().toISOString(),
        payload,
      }));
      return true;
    } catch (error) {
      return false;
    }
  }

  function clearDraft(collectionId) {
    if (!collectionId) return;
    try {
      localStorage.removeItem(storageKey(collectionId));
    } catch (error) {
      // localStorage may be unavailable; recovery should never block saving.
    }
  }

  function recoveryBanner() {
    let banner = document.querySelector("#editor-draft-recovery");
    if (banner) return banner;
    banner = document.createElement("section");
    banner.id = "editor-draft-recovery";
    banner.className = "card";
    banner.hidden = true;
    banner.setAttribute("role", "status");

    const copy = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = "Unsaved draft available";
    const detail = document.createElement("p");
    detail.className = "view-subtitle";
    copy.append(title, detail);

    const actions = document.createElement("div");
    actions.className = "view-actions";
    const restore = document.createElement("button");
    restore.type = "button";
    restore.className = "action-btn primary";
    restore.textContent = "Restore draft";
    const discard = document.createElement("button");
    discard.type = "button";
    discard.className = "action-btn secondary";
    discard.textContent = "Discard draft";
    actions.append(restore, discard);
    banner.append(copy, actions);

    const toolbar = editorForm.querySelector(".editor-toolbar");
    toolbar?.insertAdjacentElement("afterend", banner);

    restore.addEventListener("click", () => {
      const draft = readDraft(state.selectedId);
      if (!draft) {
        banner.hidden = true;
        setStatus("The saved draft is no longer available.", true);
        return;
      }
      populateEditor(draft.payload);
      setEditorDirty(true);
      banner.hidden = true;
      setStatus("Unsaved draft restored. Save changes to make it canonical.");
    });

    discard.addEventListener("click", () => {
      clearDraft(state.selectedId);
      banner.hidden = true;
      setStatus("Unsaved draft discarded.");
    });
    return banner;
  }

  function showRecoveryBanner(collectionId) {
    const banner = recoveryBanner();
    const draft = readDraft(collectionId);
    banner.hidden = !draft;
    if (!draft) return;
    const detail = banner.querySelector("p");
    const savedAt = Date.parse(draft.savedAt);
    detail.textContent = Number.isNaN(savedAt)
      ? "Restore the browser draft or discard it."
      : `Browser draft saved ${new Date(savedAt).toLocaleString()}.`;
  }

  function saveCurrentDraft() {
    autosaveTimer = null;
    if (!state.editorDirty || state.view !== "editor" || !state.current) return;
    try {
      writeDraft(state.selectedId || state.current.id, collectPayload());
    } catch (error) {
      // Incomplete transient editor state should not interrupt typing.
    }
  }

  function scheduleAutosave() {
    if (autosaveTimer !== null) clearTimeout(autosaveTimer);
    autosaveTimer = setTimeout(saveCurrentDraft, AUTOSAVE_DELAY_MS);
  }

  const originalSetEditorDirty = setEditorDirty;
  setEditorDirty = function setEditorDirtyWithDraft(dirty) {
    originalSetEditorDirty(dirty);
    if (dirty) scheduleAutosave();
  };

  const originalRenderWorkspace = renderWorkspace;
  renderWorkspace = function renderWorkspaceWithDraft(payload, ...args) {
    const saving = state.saveInFlight;
    const previousId = state.selectedId;
    const result = originalRenderWorkspace(payload, ...args);
    if (saving) {
      clearDraft(previousId);
      clearDraft(payload.id);
      recoveryBanner().hidden = true;
    } else {
      showRecoveryBanner(payload.id);
    }
    return result;
  };

  document.addEventListener("click", (event) => {
    const addQuestionButton = event.target.closest?.("#add-question");
    const removeQuestionButton = event.target.closest?.(".remove-question");
    if (!addQuestionButton && !removeQuestionButton) return;
    queueMicrotask(() => {
      if (addQuestionButton || (removeQuestionButton && !removeQuestionButton.isConnected)) {
        setEditorDirty(true);
      }
    });
  });

  window.addEventListener("beforeunload", (event) => {
    if (!state.editorDirty) return;
    event.preventDefault();
    event.returnValue = "";
  });

  globalThis.dqDraftRecovery = {
    readDraft,
    writeDraft,
    clearDraft,
    storageKey,
  };
})();
