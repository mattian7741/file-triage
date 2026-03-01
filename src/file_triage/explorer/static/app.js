(function () {
  "use strict";

  // Tag terminology: hard = manually added (explicit); soft = inherited from rules; null = neutralizes inherited (future).

  const treeEl = document.getElementById("tree");
  const listingEl = document.getElementById("listingLeft");
  const listingLeftEl = document.getElementById("listingLeft");
  const listingRightEl = document.getElementById("listingRight");
  const previewBodyEl = document.getElementById("previewBody");
  const previewFooterEl = document.getElementById("previewFooter");
  const consoleBodyEl = document.getElementById("consoleBody");
  const changesBodyEl = document.getElementById("changesBody");
  const previewPaneEl = document.getElementById("previewPane");
  const previewToggleEl = document.getElementById("previewToggle");
  const breadcrumbEl = document.getElementById("breadcrumb");
  const currentPathEl = document.getElementById("currentPathLeft");
  const currentPathLeftEl = document.getElementById("currentPathLeft");
  const currentPathRightEl = document.getElementById("currentPathRight");
  const btnUp = document.getElementById("btnUpLeft");
  const btnUpLeft = document.getElementById("btnUpLeft");
  const btnUpRight = document.getElementById("btnUpRight");
  const btnAddFolderEl = document.getElementById("btnAddFolderLeft");
  const btnAddFolderLeftEl = document.getElementById("btnAddFolderLeft");
  const btnAddFolderRightEl = document.getElementById("btnAddFolderRight");
  const dropzoneLeftEl = document.getElementById("dropzoneLeft");
  const dropzoneRightEl = document.getElementById("dropzoneRight");
  const tagsSectionEl = document.getElementById("tagsSection");
  const rulesSectionEl = document.getElementById("rulesSection");
  const sidebarDividerEl = document.getElementById("sidebarDivider");
  const selectionBarEl = document.getElementById("selectionBar");
  const selectionCountEl = document.getElementById("selectionCount");
  const batchTagInputEl = document.getElementById("batchTagInput");
  const btnBatchTagEl = document.getElementById("btnBatchTag");
  const btnClearSelectionEl = document.getElementById("btnClearSelection");
  const hideTrashCheckboxEl = document.getElementById("hideTrashCheckbox");
  const trashToggleLabelEl = document.getElementById("trashToggleLabel");
  const showNullTagsCheckboxEl = document.getElementById("showNullTagsCheckbox");

  let roots = [];
  let currentPath = null;
  let currentPathLeft = null;
  let currentPathRight = null;
  let activePane = "left";
  let currentTag = null;
  let showRulesView = false;
  let treeState = {};
  let selectedPaths = new Set();
  let showTrashed = false;  // When true, show entries with non-null vpath (moved/trashed) in listing; when false hide them
  let showNullTags = false;  // When true, tag view includes items that have the tag as null (red negating tag)
  let isTagSearchView = false;
  let tagSearchAbortController = null;
  var currentSearchMode = "matches";  // "matches" | "contains" when in tag search
  let previewPaneCollapsed = false;
  let hiddenTagSet = new Set();
  let draggedFromPane = null;  // "left" | "right" while drag in progress; used to remove scope tag when moving out of TS
  let tagsInCurrentView = new Set();
  var lastViewData = null;  // { type: 'listing'|'tagged'|'tag-search', path?: string, tag?: string, mode?: string, entries: array }
  var lastViewDataLeft = null;
  var lastViewDataRight = null;
  var previewSelectedPath = null;

  var pendingRenameTimeout = null;

  var STORAGE_KEY = "file-triage-explorer-state";

  function getPersistedState() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return {};
      var o = JSON.parse(raw);
      return o && typeof o === "object" ? o : {};
    } catch (e) {
      return {};
    }
  }

  function buildStateForSave() {
    var expandedTree = {};
    Object.keys(treeState).forEach(function (k) {
      var s = treeState[k];
      if (!s) return;
      if (s.expanded || (s.children && s.children.length)) {
        expandedTree[k] = { expanded: !!s.expanded, children: (s.children || []).map(function (c) { return { path: c.path, name: c.name }; }) };
      }
    });
    return {
      previewPaneCollapsed: previewPaneCollapsed,
      showTrashed: showTrashed,
      showNullTags: showNullTags,
      expandedTree: expandedTree,
      currentPath: currentPath,
      currentPathLeft: currentPathLeft,
      currentPathRight: currentPathRight,
      currentTag: currentTag,
      isTagSearchView: isTagSearchView,
      currentSearchMode: currentSearchMode,
    };
  }

  var saveStateTimeout = null;
  function saveStateDebounced() {
    if (saveStateTimeout) clearTimeout(saveStateTimeout);
    saveStateTimeout = setTimeout(function () {
      saveStateTimeout = null;
      try {
        var state = buildStateForSave();
        localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
      } catch (e) {}
    }, 200);
  }

  function applyPersistedState(state) {
    if (!state || typeof state !== "object") return;
    if (typeof state.previewPaneCollapsed === "boolean") previewPaneCollapsed = state.previewPaneCollapsed;
    if (typeof state.showTrashed === "boolean") showTrashed = state.showTrashed;
    if (typeof state.showNullTags === "boolean") showNullTags = state.showNullTags;
    if (state.expandedTree && typeof state.expandedTree === "object") {
      Object.keys(state.expandedTree).forEach(function (k) {
        var v = state.expandedTree[k];
        if (v && typeof v.expanded === "boolean") {
          treeState[k] = { expanded: v.expanded, children: Array.isArray(v.children) ? v.children : [], rendered: true };
        }
      });
    }
    if (state.currentPath !== undefined && state.currentPath !== null) currentPath = state.currentPath;
    if (state.currentPathLeft !== undefined && state.currentPathLeft !== null) currentPathLeft = state.currentPathLeft;
    if (state.currentPathRight !== undefined && state.currentPathRight !== null) currentPathRight = state.currentPathRight;
    if (state.currentTag !== undefined) currentTag = state.currentTag;
    if (typeof state.isTagSearchView === "boolean") isTagSearchView = state.isTagSearchView;
    if (state.currentSearchMode === "matches" || state.currentSearchMode === "contains") currentSearchMode = state.currentSearchMode;
  }

  function api(path) {
    return path.startsWith("http") ? path : "/api/" + path;
  }

  function hideTagsParam() {
    if (hiddenTagSet.size === 0) return "";
    return "&hide_tags=" + encodeURIComponent(Array.from(hiddenTagSet).join(","));
  }

  function showNullTagsParam() {
    return showNullTags ? "&show_null_tagged=1" : "";
  }

  /** Params for main-view fetches: get all data; filtering is client-side. */
  function fullDataParams() {
    return "";
  }

  function filterEntriesByVisibility(entries, currentPath, viewContext) {
    return (entries || []).filter(function (e) {
      var eff = getEffectiveTagsFromEntry(e);
      // When viewing "tagged" list for a specific tag, show entries that have that tag in effective set
      if (viewContext && viewContext.type === "tagged" && viewContext.tag) {
        if (eff.indexOf(viewContext.tag) >= 0) return true;
        if (!showNullTags && (e.tags_null || []).indexOf(viewContext.tag) >= 0) return false;
      }
      if (viewContext && viewContext.type === "tag-search" && viewContext.tag) {
        if (eff.indexOf(viewContext.tag) >= 0) return true;
        if (!showNullTags && (e.tags_null || []).indexOf(viewContext.tag) >= 0) return false;
      }
      if (e.vpath) {
        if (e.display_style === "original" && !showTrashed) return false;
        if (currentPath != null && currentPath !== "") {
          var norm = function (p) { return (p || "").replace(/\/+$/, "") || "/"; };
          var vpathParent = e.vpath.replace(/\/[^/]*$/, "") || "/";
          if (norm(currentPath) === norm(vpathParent)) return true;
        }
        if (!showTrashed) return false;
      }
      if (hiddenTagSet.size && eff.some(function (t) { return hiddenTagSet.has(t); })) return false;
      return true;
    });
  }

  function tagsInScopeFromEntries(entries) {
    var set = new Set();
    (entries || []).forEach(function (e) {
      getEffectiveTagsFromEntry(e).forEach(function (t) { set.add(t); });
    });
    return set;
  }

  function getEffectiveTagsFromEntry(e) {
    var explicit = e.tags || [];
    var inherited = e.tags_inherited || [];
    var nulls = e.tags_null || [];
    return explicit.concat(inherited.filter(function (t) { return explicit.indexOf(t) < 0 && nulls.indexOf(t) < 0; }));
  }

  function fetchJson(url) {
    return fetch(api(url)).then((r) => {
      if (!r.ok) throw new Error(r.statusText);
      return r.json();
    });
  }

  function renderTreeNode(path, name, depth, isRoot) {
    const div = document.createElement("div");
    div.className = "tree-node";
    div.dataset.path = path;
    div.style.paddingLeft = (depth * 12 + 4) + "px";

    const toggle = document.createElement("span");
    toggle.className = "toggle empty";
    toggle.textContent = " ";
    div.appendChild(toggle);

    const icon = document.createElement("span");
    icon.className = "icon";
    icon.textContent = "📁";
    div.appendChild(icon);

    const label = document.createElement("span");
    label.textContent = name || path || "/";
    label.title = path;
    div.appendChild(label);

    div.addEventListener("click", function (e) {
      e.stopPropagation();
      activePane = "left";
      navigateTo(path, "left");
    });

    return div;
  }

  function ensureTreeChildren(path, nodeEl, parentEl, depth) {
    const key = path || "/";
    if (treeState[key] && treeState[key].rendered) {
      toggleTreeExpand(path, nodeEl);
      return;
    }
    fetchJson("listing?path=" + encodeURIComponent(path || "/"))
      .then(function (data) {
        const dirs = (data.entries || []).filter(function (e) { return e.is_dir; });
        if (!treeState[key]) treeState[key] = { expanded: false, children: [] };
        treeState[key].children = dirs;
        treeState[key].rendered = true;
        treeState[key].expanded = true;
        const container = document.createElement("div");
        container.className = "tree-children";
        container.dataset.path = key;
        dirs.forEach(function (e) {
          buildTreeRec(container, e.path, e.name, depth + 1);
        });
        const next = nodeEl.nextSibling;
        if (next) parentEl.insertBefore(container, next);
        else parentEl.appendChild(container);
        const toggleSpan = nodeEl.querySelector(".toggle");
        if (toggleSpan) { toggleSpan.textContent = "▼"; toggleSpan.classList.remove("empty"); }
        nodeEl.classList.add("open");
        saveStateDebounced();
      })
      .catch(function () {});
  }

  function toggleTreeExpand(path, nodeEl) {
    const key = path || "/";
    const state = treeState[key];
    if (!state) return;
    state.expanded = !state.expanded;
    const childrenEl = treeEl.querySelector('.tree-children[data-path="' + key + '"]');
    if (childrenEl) childrenEl.style.display = state.expanded ? "block" : "none";
    const toggleSpan = nodeEl.querySelector(".toggle");
    if (toggleSpan) toggleSpan.textContent = state.expanded ? "▼" : "▶";
    toggleSpan.classList.remove("empty");
    saveStateDebounced();
  }

  function buildTreeRec(parentEl, path, name, depth) {
    const nodeEl = renderTreeNode(path, name, depth, path === null);
    parentEl.appendChild(nodeEl);

    const key = path || "/";
    const state = treeState[key];
    if (state && state.children && state.children.length) {
      const container = document.createElement("div");
      container.className = "tree-children";
      container.dataset.path = key;
      container.style.display = state.expanded ? "block" : "none";
      state.children.forEach(function (e) {
        buildTreeRec(container, e.path, e.name, depth + 1);
      });
      parentEl.appendChild(container);
      const toggleSpan = nodeEl.querySelector(".toggle");
      toggleSpan.textContent = state.expanded ? "▼" : "▶";
      toggleSpan.classList.remove("empty");
    } else {
      nodeEl.querySelector(".toggle").addEventListener("click", function (e) {
        e.stopPropagation();
        if (!treeState[key] || !treeState[key].rendered) {
          ensureTreeChildren(path, nodeEl, parentEl, depth);
          return;
        }
        toggleTreeExpand(path, nodeEl);
      });
    }
    return nodeEl;
  }

  function refreshTree() {
    treeEl.innerHTML = "";
    if (rulesSectionEl) {
      rulesSectionEl.innerHTML = "";
      const title = document.createElement("div");
      title.className = "rules-section-title";
      title.textContent = "RULES";
      rulesSectionEl.appendChild(title);
      const rulesListWrap = document.createElement("div");
      rulesListWrap.className = "rules-list-wrap";
      const div = document.createElement("div");
      div.className = "tree-node rules-node" + (showRulesView ? " selected" : "");
      div.dataset.view = "rules";
      const icon = document.createElement("span");
      icon.className = "icon";
      icon.textContent = "\uD83D\uDCCF";  /* ruler / rule icon 📐 */
      icon.setAttribute("aria-hidden", "true");
      div.appendChild(icon);
      const label = document.createElement("span");
      label.textContent = "Tagging";
      label.title = "Regex rules that tag files by full path";
      div.appendChild(label);
      div.addEventListener("click", function (e) {
        e.stopPropagation();
        navigateToRules();
      });
      rulesListWrap.appendChild(div);
      rulesSectionEl.appendChild(rulesListWrap);
    }
    buildTreeRec(treeEl, "/", "Macintosh HD", 0);
    fetchJson("listing?path=" + encodeURIComponent("/Volumes"))
      .then(function (data) {
        var dirs = (data.entries || []).filter(function (e) {
          if (!e.is_dir) return false;
          var ep = (e.vpath || e.path || "").replace(/\/$/, "") || "/";
          return ep !== "/";
        });
        dirs.sort(function (a, b) {
          var ap = (a.vpath || a.path || "").toLowerCase();
          var bp = (b.vpath || b.path || "").toLowerCase();
          return ap < bp ? -1 : ap > bp ? 1 : 0;
        });
        dirs.forEach(function (e) {
          buildTreeRec(treeEl, e.path, e.name, 0);
        });
        refreshTagsSection();
        saveStateDebounced();
      })
      .catch(function () {
        roots.filter(function (r) { return r !== "/"; }).forEach(function (r) {
          buildTreeRec(treeEl, r, r.split("/").filter(Boolean).pop() || r, 0);
        });
        refreshTagsSection();
      });
  }

  function getTagsForAutocomplete() {
    return Promise.all([
      fetch(api("tag-names")).then(function (r) { return r.ok ? r.json() : Promise.resolve({}); }).then(function (data) { return (data && data.tags) ? data.tags : []; }),
      fetch(api("rules")).then(function (r) { return r.ok ? r.json() : Promise.resolve({}); }).then(function (data) {
        const rules = (data && data.rules) ? data.rules : [];
        const set = new Set();
        rules.forEach(function (r) { (r.tags || []).forEach(function (t) { set.add(t); }); });
        return Array.from(set);
      })
    ]).then(function (results) {
      const metaTags = results[0];
      const ruleTags = results[1];
      const metaSet = new Set(metaTags);
      const hardTags = metaTags.slice().sort();
      const softTags = ruleTags.filter(function (t) { return !metaSet.has(t); });
      softTags.sort();
      return hardTags.concat(softTags);
    });
  }

  function addTagsSearchInputTo(wrapEl) {
    if (!wrapEl) return;
    wrapEl.innerHTML = "";
    wrapEl.className = "tags-search-wrap search-row";
    const select = document.createElement("select");
    select.className = "search-mode-select";
    select.setAttribute("aria-label", "Search mode");
    select.innerHTML = "<option value=\"matches\">Matches</option><option value=\"contains\">Contains</option>";
    wrapEl.appendChild(select);
    const inputWrap = document.createElement("div");
    inputWrap.className = "search-input-wrap";
    wrapEl.appendChild(inputWrap);
    const searchInput = document.createElement("input");
    searchInput.type = "text";
    searchInput.className = "tags-search-input";
    searchInput.placeholder = "tag";
    searchInput.setAttribute("aria-label", "Tag");
    searchInput.setAttribute("autocomplete", "off");
    inputWrap.appendChild(searchInput);
    const dropdown = document.createElement("div");
    dropdown.className = "search-autocomplete-dropdown";
    dropdown.setAttribute("role", "listbox");
    inputWrap.appendChild(dropdown);

    var cachedTagList = null;
    var highlightedIndex = -1;

    function hideDropdown() {
      dropdown.innerHTML = "";
      dropdown.classList.remove("visible");
      highlightedIndex = -1;
    }

    function showMatches() {
      var value = searchInput.value.trim().toLowerCase();
      function populate() {
        var list = cachedTagList || [];
        var matches = value ? list.filter(function (tag) { return tag.toLowerCase().indexOf(value) >= 0; }) : list.slice(0, 50);
        matches.sort();  /* alphabetical order: shorter/lexicographic (e.g. "list" before "listing") */
        dropdown.innerHTML = "";
        if (matches.length === 0) {
          dropdown.classList.remove("visible");
          return;
        }
        highlightedIndex = 0;
        matches.forEach(function (tag, i) {
          var item = document.createElement("div");
          item.className = "search-autocomplete-item" + (i === 0 ? " highlighted" : "");
          item.setAttribute("role", "option");
          item.textContent = tag;
          item.dataset.tag = tag;
          item.dataset.index = String(i);
          item.addEventListener("click", function (e) {
            e.preventDefault();
            e.stopPropagation();
            searchInput.value = tag;
            hideDropdown();
            searchInput.focus();
            doTagSearch(tag);
          });
          item.addEventListener("mouseenter", function () {
            dropdown.querySelectorAll(".search-autocomplete-item").forEach(function (el, j) { el.classList.toggle("highlighted", j === parseInt(el.dataset.index, 10)); });
            highlightedIndex = parseInt(item.dataset.index, 10);
          });
          dropdown.appendChild(item);
        });
        dropdown.classList.add("visible");
      }
      if (cachedTagList) {
        populate();
        return;
      }
      getTagsForAutocomplete().then(function (list) {
        cachedTagList = list;
        populate();
      }).catch(function () {
        dropdown.classList.remove("visible");
      });
    }

    searchInput.addEventListener("focus", function () {
      showMatches();
    });
    searchInput.addEventListener("input", function () {
      showMatches();
    });
    searchInput.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        hideDropdown();
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        var items = dropdown.querySelectorAll(".search-autocomplete-item");
        if (items.length === 0) return;
        highlightedIndex = (highlightedIndex + 1) % items.length;
        items.forEach(function (el, j) { el.classList.toggle("highlighted", j === highlightedIndex); });
        items[highlightedIndex].scrollIntoView({ block: "nearest" });
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        var items = dropdown.querySelectorAll(".search-autocomplete-item");
        if (items.length === 0) return;
        highlightedIndex = highlightedIndex <= 0 ? items.length - 1 : highlightedIndex - 1;
        items.forEach(function (el, j) { el.classList.toggle("highlighted", j === highlightedIndex); });
        items[highlightedIndex].scrollIntoView({ block: "nearest" });
        return;
      }
      if (e.key === "Enter") {
        var typed = searchInput.value.trim();
        var items = dropdown.querySelectorAll(".search-autocomplete-item");
        /* Exact match: typed string equals a tag in the dropdown – use it before the highlighted item */
        var exactMatch = typed && items.length > 0 && Array.from(items).find(function (el) { return el.dataset.tag.toLowerCase() === typed.toLowerCase(); });
        if (exactMatch) {
          e.preventDefault();
          hideDropdown();
          doTagSearch(exactMatch.dataset.tag);
          return;
        }
        if (items.length > 0 && highlightedIndex >= 0 && items[highlightedIndex]) {
          e.preventDefault();
          var tag = items[highlightedIndex].dataset.tag;
          searchInput.value = tag;
          hideDropdown();
          doTagSearch(tag);
          return;
        }
        if (typed) doTagSearch(typed);
      }
    });
    searchInput.addEventListener("blur", function () {
      setTimeout(function () {
        var active = document.activeElement;
        if (active && dropdown.contains(active)) return;
        hideDropdown();
      }, 150);
    });
    dropdown.addEventListener("mousedown", function (e) {
      e.preventDefault();
    });
  }

  function restoreTagsSearchInput() {
    const wrap = document.getElementById("searchWrap");
    if (wrap) addTagsSearchInputTo(wrap);
  }

  function refreshTagsSection() {
    if (!tagsSectionEl || !sidebarDividerEl) return Promise.resolve();
    tagsSectionEl.innerHTML = "";
    return Promise.all([
      fetch(api("tag-names")).then(function (r) { return r.ok ? r.json() : Promise.resolve({}); }).then(function (data) { return (data && data.tags) ? data.tags : []; }),
      fetch(api("rules")).then(function (r) { return r.ok ? r.json() : Promise.resolve({}); }).then(function (data) {
        const rules = (data && data.rules) ? data.rules : [];
        const set = new Set();
        rules.forEach(function (r) {
          (r.tags || []).forEach(function (t) { set.add(t); });
        });
        return Array.from(set);
      }),
      fetch(api("hidden-tags")).then(function (r) { return r.ok ? r.json() : Promise.resolve({}); }).then(function (data) { return (data && data.hidden_tags) ? data.hidden_tags : []; })
    ]).then(function (results) {
      const metaTags = results[0];
      const ruleTags = results[1];
      const hiddenList = results[2] || [];
      hiddenTagSet = new Set(hiddenList);
      const metaSet = new Set(metaTags);
      const hardTags = metaTags.slice().sort();
      const softTags = ruleTags.filter(function (t) { return !metaSet.has(t); });
      softTags.sort();
      const allTags = hardTags.concat(softTags);
      var inViewTags = allTags.filter(function (t) { return tagsInCurrentView.has(t); }).sort();
      var remainingHard = hardTags.filter(function (t) { return !tagsInCurrentView.has(t); });
      var remainingSoft = softTags.filter(function (t) { return !tagsInCurrentView.has(t); });
      var allTagsOrdered = inViewTags.concat(remainingHard).concat(remainingSoft);
      sidebarDividerEl.classList.add("visible");
      const title = document.createElement("div");
      title.className = "tags-section-title";
      title.textContent = "TAGS";
      tagsSectionEl.appendChild(title);
      const tagsTreeWrap = document.createElement("div");
      tagsTreeWrap.className = "tags-tree";
      allTagsOrdered.forEach(function (tag) {
        const hasHard = metaSet.has(tag);
        const isHidden = hiddenTagSet.has(tag);
        const div = document.createElement("div");
        div.className = "tree-node tag-node" + (currentTag === tag ? " selected" : "") + (hasHard ? "" : " tag-node-rule-only");
        div.dataset.tag = tag;
        const icon = document.createElement("span");
        icon.className = "icon";
        icon.textContent = "\uD83C\uDFF7";
        icon.setAttribute("aria-hidden", "true");
        div.appendChild(icon);
        const label = document.createElement("span");
        label.className = "tag-label";
        label.textContent = tag;
        label.title = hasHard ? "Files with tag: " + tag : "Tag from rules only (no files tagged yet)";
        div.appendChild(label);
        const toggleBtn = document.createElement("button");
        toggleBtn.type = "button";
        toggleBtn.className = "tag-visibility-toggle" + (isHidden ? " invisible" : "");
        toggleBtn.setAttribute("aria-label", isHidden ? "Show files with tag " + tag : "Hide files with tag " + tag);
        toggleBtn.title = isHidden ? "Visible — click to show " + tag + " in lists" : "Hidden — click to hide " + tag + " in lists";
        toggleBtn.textContent = isHidden ? "\uD83D\uDD13" : "\uD83D\uDC41";
        toggleBtn.dataset.tag = tag;
        toggleBtn.addEventListener("click", function (e) {
          e.stopPropagation();
          var sidebarEl = document.querySelector(".sidebar");
          var savedScroll = sidebarEl ? sidebarEl.scrollTop : 0;
          function restoreScrollAndRefresh() {
            return refreshTagsSection().then(function () {
              if (sidebarEl) sidebarEl.scrollTop = savedScroll;
              refreshCurrentView();
            });
          }
          if (hiddenTagSet.has(tag)) {
            fetch(api("hidden-tags") + "?tag=" + encodeURIComponent(tag), { method: "DELETE" })
              .then(function (r) { if (!r.ok) throw new Error(r.statusText); return r.json(); })
              .then(function () {
                hiddenTagSet.delete(tag);
                return restoreScrollAndRefresh();
              })
              .catch(function (err) { alert(err.message || "Failed to show tag"); });
          } else {
            fetch(api("hidden-tags"), {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ tag: tag }),
            })
              .then(function (r) { if (!r.ok) throw new Error(r.statusText); return r.json(); })
              .then(function () {
                hiddenTagSet.add(tag);
                return restoreScrollAndRefresh();
              })
              .catch(function (err) { alert(err.message || "Failed to hide tag"); });
          }
        });
        div.appendChild(toggleBtn);
        div.addEventListener("click", function (e) {
          if (e.target === toggleBtn || toggleBtn.contains(e.target)) return;
          e.stopPropagation();
          navigateToTag(tag);
        });
        tagsTreeWrap.appendChild(div);
      });
      tagsSectionEl.appendChild(tagsTreeWrap);
    }).catch(function () {
      sidebarDividerEl.classList.remove("visible");
    });
  }

  function setCurrentTag(tag, skipRefreshTagsSection) {
    currentTag = tag;
    showRulesView = false;
    if (tag) {
      var scopePath = currentPath || (roots.length ? roots[0] : "") || "/";
      if (typeof scopePath !== "string") scopePath = "/";
      if (scopePath !== "/" && scopePath.endsWith("/")) scopePath = scopePath.replace(/\/+$/, "");
      if (isTagSearchView) {
        var query = (currentSearchMode === "contains" ? "contains:" : "matches:") + tag;
        var pathDisplay = scopePath + "/?" + query;
        if (currentPathLeftEl) currentPathLeftEl.textContent = pathDisplay;
        if (currentPathRightEl) currentPathRightEl.textContent = currentPathRight || "/";
        buildBreadcrumbForScope(scopePath, "?" + query);
      } else {
        var pathDisplayTag = scopePath + "/#" + tag;
        if (currentPathLeftEl) currentPathLeftEl.textContent = pathDisplayTag;
        if (currentPathRightEl) currentPathRightEl.textContent = currentPathRight || "/";
        buildBreadcrumbForScope(scopePath, "#" + tag);
      }
      if (btnUpLeft) btnUpLeft.disabled = false;
      if (btnUpRight) btnUpRight.disabled = false;
    } else {
      if (currentPathLeftEl) currentPathLeftEl.textContent = currentPathLeft || "/";
      if (currentPathRightEl) currentPathRightEl.textContent = currentPathRight || "/";
      if (btnUpLeft) btnUpLeft.disabled = !currentPathLeft || (roots.some(function (r) { return currentPathLeft === r; }) && currentPathLeft !== "/");
      if (btnUpRight) btnUpRight.disabled = !currentPathRight || (roots.some(function (r) { return currentPathRight === r; }) && currentPathRight !== "/");
    }
    if (!skipRefreshTagsSection) refreshTagsSection();
    updateDropzoneLabels();
  }

  function buildBreadcrumbForScope(scopePath, suffix) {
    breadcrumbEl.innerHTML = "";
    var parts = (scopePath === "/" || !scopePath) ? [] : scopePath.replace(/^\/+/, "").split("/").filter(Boolean);
    var soFar = "/";
    var a0 = document.createElement("a");
    a0.href = "#";
    a0.textContent = "Root";
    a0.addEventListener("click", function (e) { e.preventDefault(); clearTagView(); if (roots[0]) navigateTo(roots[0], "left"); });
    breadcrumbEl.appendChild(a0);
    for (var i = 0; i < parts.length; i++) {
      soFar = soFar === "/" ? "/" + parts[i] : soFar + "/" + parts[i];
      var sep = document.createElement("span");
      sep.className = "sep";
      sep.textContent = " ▸ ";
      breadcrumbEl.appendChild(sep);
      var link = document.createElement("a");
      link.href = "#";
      link.textContent = parts[i];
      (function (path) {
        link.addEventListener("click", function (e) { e.preventDefault(); clearTagView(); navigateTo(path, "left"); });
      })(soFar);
      breadcrumbEl.appendChild(link);
    }
    var sepEnd = document.createElement("span");
    sepEnd.className = "sep";
    sepEnd.textContent = " ▸ ";
    breadcrumbEl.appendChild(sepEnd);
    var suffixSpan = document.createElement("span");
    suffixSpan.textContent = suffix;
    breadcrumbEl.appendChild(suffixSpan);
  }

  function updateDropzoneLabels() {
    if (dropzoneLeftEl) {
      if (currentTag && !isTagSearchView) {
        dropzoneLeftEl.textContent = "Drop here to add tag " + currentTag;
        dropzoneLeftEl.title = "Drop here to add tag " + currentTag;
      } else if (isTagSearchView) {
        dropzoneLeftEl.textContent = "Search results — drop not supported";
        dropzoneLeftEl.title = "Search results are read-only";
      } else {
        dropzoneLeftEl.textContent = "Drop here to move into this folder";
        dropzoneLeftEl.title = "Drop here to move into this folder";
      }
    }
  }

  function clearTagView() {
    currentTag = null;
    isTagSearchView = false;
    setCurrentPath(currentPathLeft, "left");
    updateDropzoneLabels();
    clearPreview();
    clearConsole();
    if (currentPathLeft) navigateTo(currentPathLeft, "left"); else navigateTo(roots[0], "left");
    if (currentPathRight) navigateTo(currentPathRight, "right"); else navigateTo(roots[0], "right");
  }

  function navigateToRules() {
    showRulesView = true;
    currentTag = null;
    lastViewData = null;
    tagsInCurrentView = new Set();
    if (currentPathLeftEl) currentPathLeftEl.textContent = "Rules";
    if (currentPathRightEl) currentPathRightEl.textContent = "Rules";
    if (btnUpLeft) btnUpLeft.disabled = false;
    if (btnUpRight) btnUpRight.disabled = false;
    breadcrumbEl.innerHTML = "";
    const span = document.createElement("span");
    span.textContent = "Rules";
    breadcrumbEl.appendChild(span);
    selectedPaths.clear();
    updateSelectionBar();
    clearPreview();
    clearConsole();
    listingLeftEl.innerHTML = '<div class="loading">Loading…</div>';
    if (listingRightEl) listingRightEl.innerHTML = "";
    fetch(api("rules"))
      .then(function (r) {
        if (!r.ok) throw new Error(r.statusText);
        return r.json();
      })
      .then(function (data) {
        const rules = (data && data.rules) || [];
        let html = '<table><thead><tr><th class="icon-cell"></th><th>Pattern</th><th class="tags-cell">Tags</th><th class="actions-cell"></th></tr></thead><tbody>';
        rules.forEach(function (r) {
          const pattern = r.pattern || "";
          const tags = r.tags || [];
          let tagsHtml = '<span class="tags-list">';
          tags.forEach(function (tag) {
            tagsHtml += '<span class="tag-pill explicit"><span class="tag-name">' + escapeHtml(tag) + '</span> <button type="button" class="tag-remove rule-tag-remove" data-pattern="' + escapeHtml(pattern) + '" data-tag="' + escapeHtml(tag) + '" aria-label="Remove tag">×</button></span>';
          });
          tagsHtml += '</span> <input type="text" class="tag-input rule-row-tag-input" placeholder="+ tag" data-pattern="' + escapeHtml(pattern) + '" size="8" />';
          html += '<tr class="row-rule" data-pattern="' + escapeHtml(pattern).replace(/"/g, "&quot;") + '">';
          html += '<td class="icon-cell">\uD83D\uDCCF</td>';
          html += '<td class="name-cell rule-pattern-cell"><span class="rule-pattern-editable" role="button" tabindex="0" data-pattern="' + escapeHtml(pattern).replace(/"/g, "&quot;") + '" title="Click to edit">' + '<code>' + escapeHtml(pattern) + '</code></span></td>';
          html += '<td class="tags-cell">' + tagsHtml + '</td>';
          html += '<td class="actions-cell"><button type="button" class="btn-trash" data-pattern="' + escapeHtml(pattern) + '" title="Delete rule">\uD83D\uDDD1</button></td></tr>';
        });
        html += '<tr class="row-rule-add"><td class="icon-cell"></td><td class="name-cell"><input type="text" id="newRulePattern" class="rule-pattern-input" placeholder="Regex (e.g. .*DS_Store.*)" size="24" /></td>';
        html += '<td class="tags-cell"><input type="text" id="newRuleTag" class="tag-input rule-tag-input" placeholder="Tag" size="10" /></td>';
        html += '<td class="actions-cell"><button type="button" class="btn btn-add-rule" id="btnAddRule">Add</button></td></tr>';
        html += "</tbody></table>";
        listingLeftEl.innerHTML = html;
        listingLeftEl.querySelectorAll(".btn-trash").forEach(function (btn) {
          btn.addEventListener("click", function (e) {
            e.stopPropagation();
            deleteRulePattern(btn.dataset.pattern);
          });
        });
        listingLeftEl.querySelectorAll(".rule-tag-remove").forEach(function (btn) {
          btn.addEventListener("click", function (e) {
            e.stopPropagation();
            deleteRule(btn.dataset.pattern, btn.dataset.tag);
          });
        });
        listingLeftEl.querySelectorAll(".rule-row-tag-input").forEach(function (input) {
          input.addEventListener("keydown", function (e) {
            if (e.key === "Enter") {
              e.preventDefault();
              const tag = input.value.trim();
              if (tag) addRule(input.dataset.pattern, tag);
            }
          });
        });
        listingLeftEl.querySelectorAll(".rule-pattern-editable").forEach(function (span) {
          span.addEventListener("click", function (e) {
            e.stopPropagation();
            startEditRulePattern(span);
          });
          span.addEventListener("keydown", function (e) {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              startEditRulePattern(span);
            }
          });
        });
        const patternInput = document.getElementById("newRulePattern");
        const tagInput = document.getElementById("newRuleTag");
        const btnAdd = document.getElementById("btnAddRule");
        if (btnAdd && patternInput && tagInput) {
          function doAdd() {
            const pattern = patternInput.value.trim();
            const tag = tagInput.value.trim();
            if (pattern && tag) addRule(pattern, tag);
          }
          btnAdd.addEventListener("click", doAdd);
          tagInput.addEventListener("keydown", function (e) {
            if (e.key === "Enter") { e.preventDefault(); doAdd(); }
          });
          patternInput.addEventListener("keydown", function (e) {
            if (e.key === "Enter") { e.preventDefault(); tagInput.focus(); }
          });
        }
      })
      .catch(function (err) {
        listingLeftEl.innerHTML = '<div class="error">' + escapeHtml(err.message || "Failed to load rules") + "</div>";
      });
    refreshTree();
  }

  function addRule(pattern, tag) {
    fetch(api("rules"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pattern: pattern, tag: tag }),
    })
      .then(function (r) { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then(function () {
        navigateToRules();
      })
      .catch(function (err) { alert(err.message || "Failed to add rule"); });
  }

  function deleteRule(pattern, tag) {
    fetch(api("rules") + "?pattern=" + encodeURIComponent(pattern) + "&tag=" + encodeURIComponent(tag), { method: "DELETE" })
      .then(function (r) { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then(function () {
        navigateToRules();
      })
      .catch(function (err) { alert(err.message || "Failed to delete rule"); });
  }

  function deleteRulePattern(pattern) {
    fetch(api("rules") + "?pattern=" + encodeURIComponent(pattern), { method: "DELETE" })
      .then(function (r) { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then(function () {
        navigateToRules();
      })
      .catch(function (err) { alert(err.message || "Failed to delete rule"); });
  }

  function startEditRulePattern(spanEl) {
    const cell = spanEl.closest("td");
    if (!cell || cell.querySelector("input.rule-pattern-edit-input")) return;
    const oldPattern = spanEl.dataset.pattern || "";
    const input = document.createElement("input");
    input.type = "text";
    input.className = "rule-pattern-input rule-pattern-edit-input";
    input.value = oldPattern;
    input.placeholder = "Regex pattern";
    cell.innerHTML = "";
    cell.appendChild(input);
    input.focus();
    input.select();
    function commit() {
      const newPattern = input.value.trim();
      if (newPattern === oldPattern) {
        cell.innerHTML = "";
        const span = document.createElement("span");
        span.className = "rule-pattern-editable";
        span.role = "button";
        span.tabIndex = 0;
        span.dataset.pattern = oldPattern;
        span.title = "Click to edit";
        const code = document.createElement("code");
        code.textContent = oldPattern;
        span.appendChild(code);
        cell.appendChild(span);
        span.addEventListener("click", function (e) { e.stopPropagation(); startEditRulePattern(span); });
        span.addEventListener("keydown", function (e) {
          if (e.key === "Enter" || e.key === " ") { e.preventDefault(); startEditRulePattern(span); }
        });
        return;
      }
      if (!newPattern) {
        cancel();
        return;
      }
      updateRulePattern(oldPattern, newPattern);
    }
    function cancel() {
      cell.innerHTML = "";
      const span = document.createElement("span");
      span.className = "rule-pattern-editable";
      span.role = "button";
      span.tabIndex = 0;
      span.dataset.pattern = oldPattern;
      span.title = "Click to edit";
      const code = document.createElement("code");
      code.textContent = oldPattern;
      span.appendChild(code);
      cell.appendChild(span);
      span.addEventListener("click", function (e) { e.stopPropagation(); startEditRulePattern(span); });
      span.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); startEditRulePattern(span); }
      });
    }
    input.addEventListener("blur", commit);
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        e.preventDefault();
        input.removeEventListener("blur", commit);
        commit();
      } else if (e.key === "Escape") {
        e.preventDefault();
        input.removeEventListener("blur", commit);
        cancel();
      }
    });
  }

  function updateRulePattern(oldPattern, newPattern) {
    fetch(api("rules"), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ old_pattern: oldPattern, new_pattern: newPattern }),
    })
      .then(function (r) { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then(function () {
        navigateToRules();
      })
      .catch(function (err) { alert(err.message || "Failed to update pattern"); });
  }

  function doTagSearch(tag) {
    const scopePath = currentPath || (roots.length ? roots[0] : "") || "/";
    var modeEl = document.querySelector(".search-mode-select");
    var searchMode = (modeEl && modeEl.value) || "matches";
    if (tagSearchAbortController) {
      tagSearchAbortController.abort();
      tagSearchAbortController = null;
    }
    currentTag = tag;
    isTagSearchView = true;
    currentSearchMode = searchMode;
    setCurrentTag(tag, true);
    tagsInCurrentView = new Set([tag]);
    refreshTagsSection();
    selectedPaths.clear();
    updateSelectionBar();

    var searchWrap = document.getElementById("searchWrap");
    if (searchWrap) {
      searchWrap.innerHTML = '<div class="loading-with-stop"><span class="loading-inline">Searching ' + escapeHtml(tag) + (searchMode === "contains" ? " (contains)" : "") + '</span> <button type="button" class="btn btn-stop-search" id="btnStopTagSearch">Stop</button></div>';
      document.getElementById("btnStopTagSearch").addEventListener("click", function () {
        if (tagSearchAbortController) {
          tagSearchAbortController.abort();
          tagSearchAbortController = null;
        }
        restoreTagsSearchInput();
      });
    }

    listingEl.innerHTML = '<table><thead><tr><th class="checkbox-cell"><input type="checkbox" class="select-all-folder" title="Select all" /></th><th class="icon-cell"></th><th>Name</th><th class="size-cell">Size</th><th class="tags-cell">Tags</th><th class="actions-cell"></th></tr></thead><tbody></tbody></table>';
    var tbody = listingEl.querySelector("tbody");
    var selectAll = listingEl.querySelector(".select-all-folder");
    if (selectAll) {
      selectAll.addEventListener("change", function () {
        var checkboxes = listingEl.querySelectorAll(".row-select");
        if (selectAll.checked) checkboxes.forEach(function (cb) { selectedPaths.add(cb.dataset.path); });
        else checkboxes.forEach(function (cb) { selectedPaths.delete(cb.dataset.path); });
        updateSelectionBar();
      });
    }

    if (consoleBodyEl) {
      consoleBodyEl.innerHTML = '<div class="search-progress-wrap">' +
        '<div class="search-progress-title">Search progress</div>' +
        '<div class="search-progress-count">0 matches</div>' +
        '<div class="search-progress-tree"></div></div>';
    }

    function renderSearchProgressTree(pathToNode, scopePath, countLabel, onToggle) {
      var treeEl = consoleBodyEl && consoleBodyEl.querySelector(".search-progress-tree");
      if (!treeEl) return;
      var countEl = consoleBodyEl && consoleBodyEl.querySelector(".search-progress-count");
      if (countEl) countEl.textContent = countLabel;
      function pathJoin(parent, name) {
        if (parent === "/") return "/" + name;
        return parent + "/" + name;
      }
      function renderNode(path) {
        var node = pathToNode[path];
        if (!node) return "";
        var children = (node.childrenNames || []).map(function (name) { return pathJoin(path, name); });
        var hasChildren = children.length > 0;
        var isExpanded = node.expanded && hasChildren;
        var classes = ["search-tree-node"];
        if (node.highlighted) classes.push("search-tree-node-highlight");
        var toggle = hasChildren ? (isExpanded ? "▼" : "▶") : "□";
        var toggleClass = hasChildren ? "search-tree-toggle" : "search-tree-toggle-empty";
        var name = node.name || path.split("/").pop() || path;
        var row = '<div class="' + classes.join(" ") + '" data-path="' + escapeHtml(path).replace(/"/g, "&quot;") + '">' +
          '<span class="' + toggleClass + '" role="button" tabindex="0">' + escapeHtml(toggle) + '</span>' +
          '<span class="search-tree-name">' + escapeHtml(name) + '</span></div>';
        if (isExpanded && children.length) {
          row += '<div class="search-tree-children">';
          children.forEach(function (childPath) {
            row += renderNode(childPath);
          });
          row += "</div>";
        }
        return row;
      }
      var rootPath = (scopePath === "/" || !scopePath) ? "/" : scopePath.replace(/\/+$/, "");
      var rootNode = pathToNode[rootPath];
      if (!rootNode) {
        treeEl.innerHTML = "";
        return;
      }
      treeEl.innerHTML = renderNode(rootPath);
      if (onToggle && typeof onToggle === "function") {
        treeEl.querySelectorAll(".search-tree-toggle").forEach(function (span) {
          if (span.classList.contains("search-tree-toggle-empty")) return;
          span.addEventListener("click", function (e) {
            e.preventDefault();
            e.stopPropagation();
            var path = span.closest(".search-tree-node").dataset.path;
            var node = pathToNode[path];
            if (node) onToggle(path, node);
          });
        });
      }
    }

    if (searchMode === "contains") {
      tagSearchAbortController = new AbortController();
      var url = api("tag-search?tag=" + encodeURIComponent(tag) + "&path=" + encodeURIComponent(scopePath) + fullDataParams() + "&report_all_tags=1&mode=contains");
      fetch(url, { signal: tagSearchAbortController.signal })
        .then(function (r) { if (!r.ok) throw new Error(r.statusText); return r.json(); })
        .then(function (data) {
          tagSearchAbortController = null;
          restoreTagsSearchInput();
          var allEntries = data.entries || [];
          lastViewData = { type: "tag-search", tag: tag, mode: "contains", entries: allEntries };
          var visible = filterEntriesByVisibility(allEntries, undefined, { type: "tag-search", tag: tag });
          tagsInCurrentView = tagsInScopeFromEntries(visible);
          refreshTagsSection();
          var sorted = visible.slice().sort(function (a, b) {
            if (a.is_dir && !b.is_dir) return -1;
            if (!a.is_dir && b.is_dir) return 1;
            var ap = (a.vpath || a.path || "").toLowerCase();
            var bp = (b.vpath || b.path || "").toLowerCase();
            return ap < bp ? -1 : ap > bp ? 1 : 0;
          });
          var html = '<table><thead><tr><th class="checkbox-cell"><input type="checkbox" class="select-all-folder" title="Select all" /></th><th class="icon-cell"></th><th>Name</th><th class="size-cell">Size</th><th class="tags-cell">Tags</th><th class="actions-cell"></th></tr></thead><tbody>';
          sorted.forEach(function (e) {
            html += buildListingRowHtml(e);
          });
          html += "</tbody></table>";
          listingEl.innerHTML = html;
          attachScopedListingRowHandlers(listingEl, "left");
          var scopePathNorm = (scopePath === "/" || !scopePath) ? "/" : scopePath.replace(/\/+$/, "");
          var pathToNode = {};
          function norm(p) { return (p === "/" || !p) ? "/" : (p + "").replace(/\/+$/, ""); }
          allEntries.forEach(function (e) {
            var path = norm(e.path);
            var name = e.name || path.split("/").pop() || path;
            pathToNode[path] = { path: path, name: name, childrenNames: [], highlighted: true, expanded: true };
          });
          allEntries.forEach(function (e) {
            var path = norm(e.path);
            var segs = path === "/" ? [] : path.split("/").filter(Boolean);
            var p = "/";
            for (var i = 0; i < segs.length; i++) {
              p = p === "/" ? "/" + segs[i] : p + "/" + segs[i];
              if (!pathToNode[p]) {
                pathToNode[p] = { path: p, name: segs[i], childrenNames: [], highlighted: false, expanded: false };
              }
            }
          });
          allEntries.forEach(function (e) {
            var path = norm(e.path);
            var p = path;
            while (p) {
              var parent = p.replace(/\/[^/]*$/, "") || "/";
              if (parent === p) break;
              if (pathToNode[parent]) pathToNode[parent].expanded = true;
              if (parent === scopePathNorm) break;
              p = parent;
            }
          });
          if (!pathToNode[scopePathNorm]) {
            pathToNode[scopePathNorm] = {
              path: scopePathNorm,
              name: scopePathNorm === "/" ? "Root" : scopePathNorm.split("/").pop(),
              childrenNames: [],
              highlighted: false,
              expanded: false
            };
          }
          Object.keys(pathToNode).sort().forEach(function (path) {
            if (path === "/" || path === scopePathNorm) return;
            var parent = path.replace(/\/[^/]*$/, "") || "/";
            var childName = path.split("/").pop();
            if (pathToNode[parent] && pathToNode[parent].childrenNames.indexOf(childName) < 0) {
              pathToNode[parent].childrenNames.push(childName);
            }
          });
          var countLabel = allEntries.length + " folder" + (allEntries.length === 1 ? "" : "s") + " contain matches";
          var onContainsToggle = function (p, node) {
            node.expanded = !node.expanded;
            renderSearchProgressTree(pathToNode, scopePathNorm, countLabel, onContainsToggle);
          };
          renderSearchProgressTree(pathToNode, scopePathNorm, countLabel, onContainsToggle);
          saveStateDebounced();
        })
        .catch(function (err) {
          tagSearchAbortController = null;
          restoreTagsSearchInput();
          if (err.name === "AbortError") return;
          listingEl.innerHTML = '<div class="error">' + escapeHtml(err.message || "Search failed") + "</div>";
        });
      return;
    }

    tagSearchAbortController = new AbortController();
    var signal = tagSearchAbortController.signal;
    var url = api("tag-search?tag=" + encodeURIComponent(tag) + "&path=" + encodeURIComponent(scopePath) + fullDataParams() + "&report_all_tags=1&mode=matches&stream=1");
    var streamedEntries = [];
    var searchTreePathToNode = {};
    var searchTreeCurrentPath = null;
    var searchTreeScopePath = (scopePath === "/" || !scopePath) ? "/" : scopePath.replace(/\/+$/, "");
    var searchDone = false;

    function pathJoin(parent, name) {
      if (parent === "/") return "/" + name;
      return parent + "/" + name;
    }

    function ensurePath(path) {
      var norm = (path === "/" || !path) ? "/" : path.replace(/\/+$/, "");
      if (searchTreePathToNode[norm]) return;
      var segs = norm === "/" ? [] : norm.split("/").filter(Boolean);
      var p = "/";
      if (!searchTreePathToNode[p]) {
        searchTreePathToNode[p] = { path: p, name: p === "/" ? "Root" : "/", childrenNames: [], highlighted: false, expanded: false, hasMatchInStrictSubtree: false };
      }
      for (var i = 0; i < segs.length; i++) {
        p = pathJoin(p, segs[i]);
        if (!searchTreePathToNode[p]) {
          searchTreePathToNode[p] = { path: p, name: segs[i], childrenNames: [], highlighted: false, expanded: false, hasMatchInStrictSubtree: false };
        }
      }
    }

    /** Matches: folder with direct child match -> highlighted; its ancestors -> expanded (match in strict subtree). */
    function setHasDirectMatchAndExpandAncestors(dirPath) {
      var norm = (dirPath === "/" || !dirPath) ? "/" : dirPath.replace(/\/+$/, "");
      var node = searchTreePathToNode[norm];
      if (node) node.highlighted = true;
      var p = norm;
      while (p) {
        var idx = p.lastIndexOf("/");
        var parent = idx <= 0 ? "/" : p.slice(0, idx);
        if (parent === p) break;
        var anc = searchTreePathToNode[parent];
        if (anc) {
          anc.hasMatchInStrictSubtree = true;
          anc.expanded = true;
        }
        if (parent === "/") break;
        p = parent;
      }
    }

      function renderSearchTree() {
        ensurePath(searchTreeScopePath);
        var n = streamedEntries.length;
        var countLabel = n + " match" + (n === 1 ? "" : "es");
        if (searchDone) countLabel = "Search complete. " + countLabel;
        renderSearchProgressTree(searchTreePathToNode, searchTreeScopePath, countLabel, function (p, node) {
          node.expanded = !node.expanded;
          renderSearchTree();
        });
    }

    fetch(url, { signal: signal })
      .then(function (response) {
        if (!response.ok) throw new Error(response.statusText);
        return response.body.getReader();
      })
      .then(function (reader) {
        var decoder = new TextDecoder();
        var buffer = "";
        function processLine(line) {
          if (!line.trim()) return;
          try {
            var obj = JSON.parse(line);
            if (obj.type === "progress" && obj.path) {
              var path = (obj.path === "/" || !obj.path) ? "/" : obj.path.replace(/\/+$/, "");
              var children = Array.isArray(obj.children) ? obj.children : [];
              ensurePath(path);
              var node = searchTreePathToNode[path];
              if (node) {
                node.childrenNames = children;
                node.expanded = !!node.hasMatchInStrictSubtree;
              }
              if (searchTreeCurrentPath && searchTreeCurrentPath !== path) {
                var prev = searchTreePathToNode[searchTreeCurrentPath];
                if (prev) prev.expanded = !!prev.hasMatchInStrictSubtree;
              }
              searchTreeCurrentPath = path;
              renderSearchTree();
            } else if (obj.type === "entry" && obj.entry) {
              streamedEntries.push(obj.entry);
              if (tbody) {
                var rowHtml = buildListingRowHtml(obj.entry);
                tbody.insertAdjacentHTML("beforeend", rowHtml);
                var newTr = tbody.querySelector("tr:last-child");
                if (newTr) attachScopedListingRowHandlersForRow(newTr, "left");
              }
              var entryPath = obj.entry.path;
              var dirPath = obj.entry.is_dir ? entryPath : entryPath.split("/").slice(0, -1).join("/") || "/";
              setHasDirectMatchAndExpandAncestors(dirPath);
              renderSearchTree();
            } else if (obj.type === "done") {
              searchDone = true;
              if (searchTreeCurrentPath) {
                var prev = searchTreePathToNode[searchTreeCurrentPath];
                if (prev) prev.expanded = !!prev.hasMatchInStrictSubtree;
                searchTreeCurrentPath = null;
              }
              lastViewData = { type: "tag-search", tag: tag, mode: "matches", entries: streamedEntries };
              var visible = filterEntriesByVisibility(streamedEntries, undefined, { type: "tag-search", tag: tag });
              tagsInCurrentView = tagsInScopeFromEntries(visible);
              refreshTagsSection();
              listingEl.innerHTML = "";
              renderTagViewTable(visible);
              if (previewFooterEl) previewFooterEl.textContent = "";
              renderSearchTree();
              saveStateDebounced();
            }
          } catch (err) {}
        }
        function readChunk() {
          return reader.read().then(function (result) {
            if (result.done) {
              if (buffer.trim()) processLine(buffer);
              tagSearchAbortController = null;
              restoreTagsSearchInput();
              if (streamedEntries.length >= 0 && !lastViewData) {
                searchDone = true;
                if (searchTreeCurrentPath) {
                  var prev = searchTreePathToNode[searchTreeCurrentPath];
                  if (prev) prev.expanded = !!prev.hasMatchInStrictSubtree;
                  searchTreeCurrentPath = null;
                }
                lastViewData = { type: "tag-search", tag: tag, mode: "matches", entries: streamedEntries };
                var visible = filterEntriesByVisibility(streamedEntries, undefined, { type: "tag-search", tag: tag });
                tagsInCurrentView = tagsInScopeFromEntries(visible);
                refreshTagsSection();
                listingEl.innerHTML = "";
                renderTagViewTable(visible);
                if (previewFooterEl) previewFooterEl.textContent = "";
                renderSearchTree();
                saveStateDebounced();
              }
              return;
            }
            buffer += decoder.decode(result.value, { stream: true });
            var lines = buffer.split("\n");
            buffer = lines.pop();
            lines.forEach(processLine);
            return readChunk();
          });
        }
        return readChunk();
      })
      .catch(function (err) {
        tagSearchAbortController = null;
        restoreTagsSearchInput();
        if (err.name === "AbortError") {
          var countEl = consoleBodyEl && consoleBodyEl.querySelector(".search-progress-count");
          if (countEl) countEl.textContent = "Search stopped.";
          return;
        }
        listingEl.innerHTML = '<div class="error">' + escapeHtml(err.message || "Search failed") + "</div>";
      });
  }

  /** Attach row click/dblclick/select handlers for tag or search scope listing. Same as folder listing but row click does not call setCurrentPath when currentTag or isTagSearchView. */
  function attachScopedListingRowHandlers(listEl, pane) {
    if (!listEl) return;
    listEl.querySelectorAll("tbody tr[data-path]").forEach(function (tr) {
      attachScopedListingRowHandlersForRow(tr, pane);
    });
    var selectAll = listEl.querySelector(".select-all-folder");
    if (selectAll) {
      selectAll.addEventListener("change", function () {
        var checkboxes = listEl.querySelectorAll(".row-select");
        if (selectAll.checked) checkboxes.forEach(function (cb) { selectedPaths.add(cb.dataset.path); });
        else checkboxes.forEach(function (cb) { selectedPaths.delete(cb.dataset.path); });
        updateSelectionBar();
      });
    }
    listEl.querySelectorAll(".row-select").forEach(function (cb) {
      cb.addEventListener("click", function (e) { e.stopPropagation(); });
      cb.addEventListener("change", function () {
        if (cb.checked) selectedPaths.add(cb.dataset.path); else selectedPaths.delete(cb.dataset.path);
        updateSelectionBar();
      });
    });
  }

  function attachScopedListingRowHandlersForRow(tr, pane) {
    tr.addEventListener("click", function (e) {
      if (e.target.closest(".tags-cell") || e.target.closest(".checkbox-cell") || e.target.closest(".actions-cell")) return;
      if (e.target.closest("input.rename-input")) return;
      activePane = pane;
      if (!currentTag && !isTagSearchView) setCurrentPath(activePane === "left" ? currentPathLeft : currentPathRight, activePane);
      selectListingRow(tr, pane);
    });
    if (tr.classList.contains("row-dir")) {
      tr.addEventListener("dblclick", function (e) {
        if (e.target.closest(".tags-cell") || e.target.closest(".checkbox-cell") || e.target.closest(".actions-cell")) return;
        if (e.target.closest("input.rename-input")) return;
        var destPath = getRowNavigatePath(tr);
        if (destPath) navigateTo(destPath, pane);
      });
    }
    var cb = tr.querySelector(".row-select");
    if (cb) {
      cb.addEventListener("click", function (e) { e.stopPropagation(); });
      cb.addEventListener("change", function () {
        if (cb.checked) selectedPaths.add(cb.dataset.path); else selectedPaths.delete(cb.dataset.path);
        updateSelectionBar();
      });
    }
  }

  function renderTagViewTable(entries) {
    var html = '<table><thead><tr><th class="checkbox-cell"><input type="checkbox" class="select-all-folder" title="Select all" /></th><th class="icon-cell"></th><th>Name</th><th class="size-cell">Size</th><th class="tags-cell">Tags</th><th class="actions-cell"></th></tr></thead><tbody>';
    var sorted = (entries || []).slice().sort(function (a, b) {
      if (a.is_dir && !b.is_dir) return -1;
      if (!a.is_dir && b.is_dir) return 1;
      var ap = (a.vpath || a.path || "").toLowerCase();
      var bp = (b.vpath || b.path || "").toLowerCase();
      return ap < bp ? -1 : ap > bp ? 1 : 0;
    });
    sorted.forEach(function (e) {
      html += buildListingRowHtml(e);
    });
    html += "</tbody></table>";
    listingEl.innerHTML = html;
    attachScopedListingRowHandlers(listingEl, "left");
  }

  /** Navigate path for an entry: vpath if set, else path. Use for all navigation (no special handling by color). */
  function getRowNavigatePath(tr) {
    return (tr && tr.dataset && (tr.dataset.vpath || tr.dataset.path)) || "";
  }

  function buildListingRowHtml(e) {
    const rowClass = (e.is_dir ? "row-dir" : "") + (e.virtual ? " row-virtual" : "") +
      (e.display_style === "original" ? " row-original" : "") + (e.display_style === "moved_here" ? " row-moved-here" : "") +
      (e.vpath ? " row-has-vpath" : "");
    const isEmpty = (e.is_dir && e.empty) || (!e.is_dir && (e.size === 0 || e.size === undefined));
    const rowEmptyClass = isEmpty ? " row-empty" : "";
    const icon = e.is_dir ? "📁" : "📄";
    const explicitTags = e.tags || [];
    const inheritedTags = e.tags_inherited || [];
    const nullTags = e.tags_null || [];
    const effective = explicitTags.concat(inheritedTags.filter(function (t) { return explicitTags.indexOf(t) < 0 && nullTags.indexOf(t) < 0; }));
    const inVtrash = e.vpath && String(e.vpath).indexOf("__VTRASH/") === 0;
    const checked = selectedPaths.has(e.path) ? ' checked="checked"' : "";
    const sizeStr = formatSize(e.size, e.is_dir);
    let tagsHtml = '<span class="tags-list">';
    explicitTags.forEach(function (tag) {
      tagsHtml += '<span class="tag-pill explicit tag-pill-hard" role="button" tabindex="0" data-path="' + escapeHtml(e.path) + '" data-tag="' + escapeHtml(tag) + '" title="Hard tag — click to make null"><span class="tag-name">' + escapeHtml(tag) + '</span> <button type="button" class="tag-remove" data-path="' + escapeHtml(e.path) + '" data-tag="' + escapeHtml(tag) + '" aria-label="Remove tag">×</button></span>';
    });
    inheritedTags.forEach(function (tag) {
      if (explicitTags.indexOf(tag) >= 0 || nullTags.indexOf(tag) >= 0) return;
      tagsHtml += '<span class="tag-pill tag-pill-soft" role="button" tabindex="0" data-path="' + escapeHtml(e.path) + '" data-tag="' + escapeHtml(tag) + '" title="Soft tag — click to make hard">' + '<span class="tag-name">' + escapeHtml(tag) + '</span></span>';
    });
    nullTags.forEach(function (tag) {
      tagsHtml += '<span class="tag-pill tag-pill-null" role="button" tabindex="0" data-path="' + escapeHtml(e.path) + '" data-tag="' + escapeHtml(tag) + '" title="Null tag — click to make hard"><span class="tag-name">' + escapeHtml(tag) + '</span></span>';
    });
    tagsHtml += '</span> <input type="text" class="tag-input" placeholder="+ tag" data-path="' + escapeHtml(e.path) + '" size="8" />';
    var dataVpath = e.vpath ? ' data-vpath="' + (e.vpath || "").replace(/"/g, "&quot;") + '"' : '';
    var isOriginal = e.display_style === "original";
    var actionBtn = isOriginal
      ? '<button type="button" class="btn-restore" data-path="' + escapeHtml(e.path) + '" title="Restore to here (clear vpath)" aria-label="Restore">\u21A9</button>'
      : '<button type="button" class="btn-trash" data-path="' + escapeHtml(e.path) + '" title="Move to trash" aria-label="Move to trash"' + (inVtrash ? ' disabled' : '') + '>\uD83D\uDDD1</button>';
    return '<tr class="' + rowClass + rowEmptyClass + '" data-path="' + (e.path || "").replace(/"/g, "&quot;") + '" data-isdir="' + e.is_dir + '"' + (e.virtual ? ' data-virtual="true"' : '') + dataVpath + ' draggable="true">' +
      '<td class="checkbox-cell"><input type="checkbox" class="row-select" data-path="' + escapeHtml(e.path) + '"' + checked + ' /></td>' +
      '<td class="icon-cell">' + icon + '</td>' +
      '<td class="name-cell"><span class="name-cell-text" title="Click to rename">' + escapeHtml(e.name) + '</span></td>' +
      '<td class="size-cell">' + escapeHtml(sizeStr) + '</td>' +
      '<td class="tags-cell">' + tagsHtml + '</td>' +
      '<td class="actions-cell">' + actionBtn + '</td></tr>';
  }

  function renderListingFromEntries(entries, path, listEl, pane) {
    listEl = listEl || listingLeftEl;
    pane = pane || "left";
    var html = '<table><thead><tr><th class="checkbox-cell"><input type="checkbox" class="select-all-folder" title="Select all" /></th><th class="icon-cell"></th><th>Name</th><th class="size-cell">Size</th><th class="tags-cell">Tags</th><th class="actions-cell"></th></tr></thead><tbody>';
    var sorted = (entries || []).slice().sort(function (a, b) {
      if (a.is_dir && !b.is_dir) return -1;
      if (!a.is_dir && b.is_dir) return 1;
      var ap = (a.vpath || a.path || "").toLowerCase();
      var bp = (b.vpath || b.path || "").toLowerCase();
      return ap < bp ? -1 : ap > bp ? 1 : 0;
    });
    sorted.forEach(function (e) {
      html += buildListingRowHtml(e);
    });
    html += "</tbody></table>";
    listEl.innerHTML = html;
    listEl.querySelectorAll("tbody tr[data-path]").forEach(function (tr) {
      tr.addEventListener("click", function (e) {
        if (e.target.closest(".tags-cell") || e.target.closest(".checkbox-cell") || e.target.closest(".actions-cell")) return;
        if (e.target.closest("input.rename-input")) return;
        activePane = pane;
        setCurrentPath(activePane === "left" ? currentPathLeft : currentPathRight, activePane);
        selectListingRow(tr, pane);
      });
    });
    listEl.querySelectorAll("tbody tr.row-dir").forEach(function (tr) {
      tr.addEventListener("dblclick", function (e) {
        if (e.target.closest(".tags-cell") || e.target.closest(".checkbox-cell") || e.target.closest(".actions-cell")) return;
        if (e.target.closest("input.rename-input")) return;
        var destPath = getRowNavigatePath(tr);
        if (destPath) navigateTo(destPath, pane);
      });
    });
    var selectAll = listEl.querySelector(".select-all-folder");
    if (selectAll) {
      selectAll.addEventListener("change", function () {
        var checkboxes = listEl.querySelectorAll(".row-select");
        if (selectAll.checked) checkboxes.forEach(function (cb) { selectedPaths.add(cb.dataset.path); });
        else checkboxes.forEach(function (cb) { selectedPaths.delete(cb.dataset.path); });
        updateSelectionBar();
      });
    }
    listEl.querySelectorAll(".row-select").forEach(function (cb) {
      cb.addEventListener("click", function (e) { e.stopPropagation(); });
      cb.addEventListener("change", function () {
        if (cb.checked) selectedPaths.add(cb.dataset.path); else selectedPaths.delete(cb.dataset.path);
        updateSelectionBar();
      });
    });
  }

  function clearPreview() {
    if (!previewBodyEl) return;
    previewBodyEl.innerHTML = "";
    previewSelectedPath = null;
    if (previewFooterEl) {
      previewFooterEl.textContent = "";
    }
  }

  function clearConsole() {
    if (consoleBodyEl) consoleBodyEl.innerHTML = "";
  }

  /** Build union of moved items under either pane scope (recursive) and render in CHANGES pane. */
  function refreshChangesPane() {
    if (!changesBodyEl) return;
    var scopeLeft = currentPathLeft || "";
    var scopeRight = currentPathRight || "";
    var url = api("changes?scope_left=" + encodeURIComponent(scopeLeft) + "&scope_right=" + encodeURIComponent(scopeRight));
    fetch(url)
      .then(function (r) { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then(function (data) {
        var lines = (data.changes || []).slice();
        lines.sort(function (a, b) {
          var c = (a.path || "").localeCompare(b.path || "");
          if (c !== 0) return c;
          return (a.vpath || "").localeCompare(b.vpath || "");
        });
        if (lines.length === 0) {
          changesBodyEl.innerHTML = "<span class=\"changes-empty\">No moved items under current folder scopes.</span>";
          return;
        }
        var html = "<table class=\"changes-table\"><thead><tr><th class=\"changes-th-source\">Source</th><th class=\"changes-th-target\">Target</th><th class=\"changes-th-action\"></th></tr></thead><tbody>";
        lines.forEach(function (line) {
          var pathAttr = (line.path || "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
          var vpathAttr = (line.vpath || "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
          html += "<tr><td class=\"change-path-red\" title=\"" + pathAttr + "\">" + escapeHtml(line.path) + "</td><td class=\"change-path-blue\" title=\"" + vpathAttr + "\">" + escapeHtml(line.vpath) + "</td><td class=\"changes-action-cell\"><button type=\"button\" class=\"btn-restore btn-restore-change\" data-path=\"" + (line.path || "").replace(/"/g, "&quot;") + "\" title=\"Restore (clear vpath)\" aria-label=\"Restore\">\u21A9</button></td></tr>";
        });
        html += "</tbody></table>";
        changesBodyEl.innerHTML = html;
        changesBodyEl.querySelectorAll(".btn-restore-change").forEach(function (btn) {
          btn.addEventListener("click", function () {
            var path = btn.getAttribute("data-path");
            if (!path) return;
            fetch(api("move"), {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ path: path, vpath: "" }),
            })
              .then(function (r) {
                if (!r.ok) return r.json().then(function (d) {
            var msg = (d.error && d.error.message) || d.error || r.statusText;
            throw new Error(typeof msg === "string" ? msg : "Request failed");
          });
                return r.json();
              })
              .then(function () {
                refreshAfterMoveOrRestore();
              })
              .catch(function (err) { alert(err.message || "Restore failed"); });
          });
        });
      })
      .catch(function () {
        changesBodyEl.innerHTML = "<span class=\"changes-empty\">Unable to load changes.</span>";
      });
  }

  function loadPreviewForPath(path) {
    if (!previewBodyEl || !path) {
      clearPreview();
      return;
    }
    if (previewPaneCollapsed) {
      return;
    }
    previewBodyEl.innerHTML = '<div class="preview-placeholder">Loading preview…</div>';
    if (previewFooterEl) previewFooterEl.textContent = "";
    fetch(api("preview?path=" + encodeURIComponent(path)))
      .then(function (r) { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then(function (data) {
        if (!data || data.kind === "none") {
          clearPreview();
          return;
        }
        if (data.kind === "unsupported") {
          clearPreview();
          return;
        }
        if (data.kind === "text") {
          previewBodyEl.innerHTML = '<pre class="preview-text">' + escapeHtml(data.content || "") + '</pre>';
          if (previewFooterEl) {
            previewFooterEl.textContent = data.truncated ? "Truncated: 100 KB" : "";
          }
          return;
        }
        if (data.kind === "image") {
          previewBodyEl.innerHTML = '<img src="' + escapeHtml(data.url || "") + '" alt="Preview" class="preview-image">';
          if (previewFooterEl) previewFooterEl.textContent = "";
          return;
        }
        if (data.kind === "video") {
          previewBodyEl.innerHTML = '<video src="' + escapeHtml(data.url || "") + '" controls preload="metadata" class="preview-video"></video>';
          if (previewFooterEl) previewFooterEl.textContent = "";
          return;
        }
        if (data.kind === "error") {
          previewBodyEl.innerHTML = "";
          if (previewFooterEl) previewFooterEl.textContent = (data.error && data.error.message) || (typeof data.error === "string" ? data.error : null) || "Failed to load preview.";
          return;
        }
        clearPreview();
      })
      .catch(function (err) {
        previewBodyEl.innerHTML = "";
        if (previewFooterEl) previewFooterEl.textContent = err.message || "Failed to load preview.";
      });
  }

  function selectPreviewRow(tr) {
    if (!tr) return;
    if (tr.dataset.isdir === "true" || tr.dataset.isdir === "True") return;
    var path = tr.dataset.path;
    if (!path) return;
    [listingLeftEl, listingRightEl].forEach(function (el) {
      if (el) el.querySelectorAll("tr.row-selected").forEach(function (row) { row.classList.remove("row-selected"); });
    });
    tr.classList.add("row-selected");
    previewSelectedPath = path;
    if (!previewPaneCollapsed) {
      loadPreviewForPath(path);
    }
  }

  /** Select a listing row (highlight only). Single-click behavior for both folders and files. Do not change scope when in tag or search scope. */
  function selectListingRow(tr, pane) {
    if (!tr || !tr.dataset || !tr.dataset.path) return;
    [listingLeftEl, listingRightEl].forEach(function (el) {
      if (el) el.querySelectorAll("tr.row-selected").forEach(function (row) { row.classList.remove("row-selected"); });
    });
    tr.classList.add("row-selected");
    activePane = pane;
    if (!currentTag && !isTagSearchView) setCurrentPath(pane === "left" ? currentPathLeft : currentPathRight, pane);
    if (tr.dataset.isdir === "true" || tr.dataset.isdir === "True") {
      previewSelectedPath = null;
      return;
    }
    previewSelectedPath = tr.dataset.path;
    if (!previewPaneCollapsed) loadPreviewForPath(tr.dataset.path);
  }

  function startInlineRename(row, pane) {
    var nameCell = row.querySelector(".name-cell");
    var span = nameCell && nameCell.querySelector(".name-cell-text");
    if (!span) return;
    var originalName = span.textContent || "";
    var input = document.createElement("input");
    input.type = "text";
    input.className = "rename-input";
    input.value = originalName;
    input.dataset.originalName = originalName;
    input.setAttribute("aria-label", "New name");
    span.parentNode.replaceChild(input, span);
    var measure = document.createElement("span");
    measure.style.cssText = "position:absolute;visibility:hidden;white-space:pre;font:inherit;font-weight:500;";
    measure.textContent = originalName || " ";
    nameCell.appendChild(measure);
    var w = measure.offsetWidth;
    measure.parentNode.removeChild(measure);
    input.style.width = Math.max(w + 16, 48) + "px";
    input.focus();
    input.select();
    function listingPath() {
      if (currentTag || isTagSearchView) {
        var p = (row.dataset.path || "").replace(/\\/g, "/");
        var idx = p.lastIndexOf("/");
        return idx <= 0 ? "/" : p.slice(0, idx);
      }
      return ((pane === "left" ? currentPathLeft : currentPathRight) || "/").replace(/\/$/, "") || "/";
    }
    function replaceWithSpan(text) {
      var s = document.createElement("span");
      s.className = "name-cell-text";
      s.title = "Click to rename";
      s.textContent = text;
      input.parentNode.replaceChild(s, input);
    }
    function commit() {
      var newName = input.value.trim();
      if (!newName || newName === originalName) {
        replaceWithSpan(originalName);
        return;
      }
      var path = row.dataset.path;
      var newVpath = (listingPath() === "/" ? "/" : listingPath() + "/") + newName;
      fetch(api("move"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: path, vpath: newVpath }),
      })
        .then(function (r) {
          if (!r.ok) return r.json().then(function (d) {
            var msg = (d.error && d.error.message) || d.error || r.statusText;
            throw new Error(typeof msg === "string" ? msg : "Request failed");
          });
          return r.json();
        })
        .then(function () {
          replaceWithSpan(newName);
          if (currentTag) {
            if (isTagSearchView) doTagSearch(currentTag);
            else navigateToTag(currentTag);
          } else {
            if (currentPathLeft) navigateTo(currentPathLeft, "left", true);
            if (currentPathRight) navigateTo(currentPathRight, "right", true);
          }
        })
        .catch(function (err) {
          alert(err.message || "Rename failed");
          replaceWithSpan(originalName);
        });
    }
    input.addEventListener("blur", function () {
      var inputEl = input;
      var rowEl = row;
      var orig = originalName;
      setTimeout(function () {
        if (!inputEl.parentNode) return;
        var active = document.activeElement;
        if (active && rowEl.contains(active) && active !== inputEl && !inputEl.contains(active)) {
          replaceWithSpan(orig);
          return;
        }
        commit();
      }, 0);
    });
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { e.preventDefault(); input.blur(); }
      else if (e.key === "Escape") { e.preventDefault(); replaceWithSpan(originalName); input.blur(); }
    });
  }

  function abortRenameInRow(row) {
    var nameCell = row && row.querySelector(".name-cell");
    var input = nameCell && nameCell.querySelector("input.rename-input");
    if (!input) return;
    var originalName = input.dataset.originalName || input.value;
    var span = document.createElement("span");
    span.className = "name-cell-text";
    span.title = "Click to rename";
    span.textContent = originalName;
    input.parentNode.replaceChild(span, input);
  }

  /** Select a row by path (adds row-selected, loads preview if file). path is the navigate path (vpath or path). */
  function selectRowByPath(path) {
    if (!path) return;
    var listEls = [listingLeftEl, listingRightEl].filter(Boolean);
    var tr = null;
    var listEl = null;
    for (var L = 0; L < listEls.length; L++) {
      var rows = listEls[L].querySelectorAll("tbody tr[data-path]");
      for (var i = 0; i < rows.length; i++) {
        if (getRowNavigatePath(rows[i]) === path) { tr = rows[i]; listEl = listEls[L]; break; }
      }
      if (tr) break;
    }
    if (!tr || !listEl) return;
    listEls.forEach(function (el) {
      el.querySelectorAll("tr.row-selected").forEach(function (row) { row.classList.remove("row-selected"); });
    });
    tr.classList.add("row-selected");
    previewSelectedPath = tr.dataset.path;
    if (tr.dataset.isdir !== "true" && tr.dataset.isdir !== "True" && !previewPaneCollapsed) loadPreviewForPath(tr.dataset.path);
    tr.scrollIntoView({ block: "nearest" });
  }

  /** Activate a listing row: navigate if folder (to vpath || path), select+preview if file. */
  function activateListingRow(tr, pane) {
    if (!tr || !tr.dataset || !tr.dataset.path) return;
    if (!pane) pane = listingLeftEl && tr.closest && tr.closest("#listingLeft") ? "left" : "right";
    if (tr.dataset.isdir === "true" || tr.dataset.isdir === "True") {
      var destPath = getRowNavigatePath(tr);
      if (destPath) navigateTo(destPath, pane);
      return;
    }
    selectPreviewRow(tr);
  }

  /** Re-fetch and re-render one pane's folder listing. Does not change currentTag or the other pane. */
  function refreshPaneListing(pane) {
    var path = pane === "left" ? currentPathLeft : currentPathRight;
    if (!path) return Promise.resolve();
    var listEl = pane === "left" ? listingLeftEl : listingRightEl;
    var url = "listing?path=" + encodeURIComponent(path) + fullDataParams() + "&report_all_tags=1&_=" + Date.now();
    return fetchJson(url)
      .then(function (data) {
        var allEntries = data.entries || [];
        var viewData = { type: "listing", path: path, entries: allEntries };
        if (pane === "left") lastViewDataLeft = viewData; else lastViewDataRight = viewData;
        var visible = filterEntriesByVisibility(allEntries, path);
        if (pane === "left") {
          tagsInCurrentView = tagsInScopeFromEntries(visible);
          refreshTagsSection();
        }
        renderListingFromEntries(visible, path, listEl, pane);
        refreshChangesPane();
      })
      .catch(function () {});
  }

  /** Refresh both panes after a move or restore, preserving scope (TS/SRS left pane stays in scope). */
  function refreshAfterMoveOrRestore() {
    if (currentTag) {
      if (isTagSearchView) doTagSearch(currentTag);
      else navigateToTag(currentTag);
      refreshPaneListing("right");
    } else {
      if (currentPathLeft != null) navigateTo(currentPathLeft, "left", true);
      if (currentPathRight != null) navigateTo(currentPathRight, "right", true);
    }
  }

  function refreshCurrentView() {
    if (currentTag) {
      if (lastViewData && lastViewData.entries) {
        var viewCtx = (lastViewData.type === "tagged" && lastViewData.tag) ? { type: "tagged", tag: lastViewData.tag } : (lastViewData.type === "tag-search" && lastViewData.tag ? { type: "tag-search", tag: lastViewData.tag } : undefined);
        var visible = filterEntriesByVisibility(lastViewData.entries, lastViewData.path, viewCtx);
        renderTagViewTable(visible);
      }
      if (tagsInCurrentView) refreshTagsSection();
      return;
    }
    if (lastViewDataLeft && lastViewDataLeft.entries) {
      var visibleLeft = filterEntriesByVisibility(lastViewDataLeft.entries, lastViewDataLeft.path);
      renderListingFromEntries(visibleLeft, lastViewDataLeft.path, listingLeftEl, "left");
    }
    if (lastViewDataRight && lastViewDataRight.entries) {
      var visibleRight = filterEntriesByVisibility(lastViewDataRight.entries, lastViewDataRight.path);
      renderListingFromEntries(visibleRight, lastViewDataRight.path, listingRightEl, "right");
    }
    if (lastViewDataLeft || lastViewDataRight) {
      var visible = lastViewDataLeft ? filterEntriesByVisibility(lastViewDataLeft.entries, lastViewDataLeft.path) : filterEntriesByVisibility(lastViewDataRight.entries, lastViewDataRight.path);
      tagsInCurrentView = tagsInScopeFromEntries(visible);
      refreshTagsSection();
    }
    refreshChangesPane();
  }

  function navigateToTag(tag) {
    const isRefresh = (tag === currentTag);
    const savedScroll = isRefresh ? listingLeftEl.scrollTop : null;
    currentTag = tag;
    isTagSearchView = false;
    setCurrentTag(tag);
    selectedPaths.clear();
    updateSelectionBar();
    clearPreview();
    clearConsole();
    listingLeftEl.innerHTML = '<div class="loading">Loading…</div>';
    return fetchJson("tagged?tag=" + encodeURIComponent(tag) + fullDataParams() + "&report_all_tags=1")
      .then(function (data) {
        var allEntries = data.entries || [];
        lastViewData = { type: "tagged", tag: tag, entries: allEntries };
        var visible = filterEntriesByVisibility(allEntries, undefined, { type: "tagged", tag: tag });
        tagsInCurrentView = tagsInScopeFromEntries(visible);
        refreshTagsSection();
        renderTagViewTable(visible);
        if (savedScroll != null) listingLeftEl.scrollTop = savedScroll;
        saveStateDebounced();
      })
      .catch(function (err) {
        listingLeftEl.innerHTML = '<div class="error">' + escapeHtml(err.message || "Failed to load") + "</div>";
      });
  }

  function setCurrentPath(path, pane) {
    pane = pane || "left";
    if (pane === "left") {
      currentPathLeft = path;
      currentPath = path;
      if (currentPathLeftEl) currentPathLeftEl.textContent = path || "/";
      if (btnUpLeft) btnUpLeft.disabled = (path == null);
      if (btnAddFolderLeftEl) btnAddFolderLeftEl.disabled = (path == null);
    } else {
      currentPathRight = path;
      if (currentPathRightEl) currentPathRightEl.textContent = path || "/";
      if (btnUpRight) btnUpRight.disabled = (path == null);
      if (btnAddFolderRightEl) btnAddFolderRightEl.disabled = (path == null);
    }
    currentTag = null;
    showRulesView = false;

    var pathForBreadcrumb = activePane === "left" ? currentPathLeft : currentPathRight;
    breadcrumbEl.innerHTML = "";
    if (pathForBreadcrumb == null || pathForBreadcrumb === "") return;
    var root = roots.filter(function (r) { return pathForBreadcrumb === r || (pathForBreadcrumb && pathForBreadcrumb.startsWith(r + "/")); })[0];
    if (!root) root = pathForBreadcrumb ? pathForBreadcrumb.split("/")[0] + "/" : "/";
    var rest = root && pathForBreadcrumb && pathForBreadcrumb.length > root.length ? pathForBreadcrumb.slice(root.length).split("/").filter(Boolean) : [];
    var label0 = root === "/" ? "Root" : root.split("/").filter(Boolean).pop() || root;
    var a0 = document.createElement("a");
    a0.href = "#";
    a0.textContent = label0;
    a0.addEventListener("click", function (e) { e.preventDefault(); navigateTo(root, activePane); });
    breadcrumbEl.appendChild(a0);
    for (var i = 0; i < rest.length; i++) {
      var sep = document.createElement("span");
      sep.className = "sep";
      sep.textContent = " ▸ ";
      breadcrumbEl.appendChild(sep);
      var segPath = root + rest.slice(0, i + 1).join("/");
      var aa = document.createElement("a");
      aa.href = "#";
      aa.textContent = rest[i];
      aa.addEventListener("click", function (p) { return function (e) { e.preventDefault(); navigateTo(p, activePane); }; }(segPath));
      breadcrumbEl.appendChild(aa);
    }
  }

  function navigateTo(path, pane, skipCache) {
    pane = pane || "left";
    var listEl = pane === "left" ? listingLeftEl : listingRightEl;
    var currentPathForPane = pane === "left" ? currentPathLeft : currentPathRight;
    var p = path || "/";
    const isRefresh = (p === currentPathForPane && !currentTag);
    const savedScroll = isRefresh ? listEl.scrollTop : null;
    currentTag = null;
    setCurrentPath(p, pane);
    selectedPaths.clear();
    updateSelectionBar();
    clearPreview();
    clearConsole();
    listEl.innerHTML = '<div class="loading">Loading…</div>';
    var url = "listing?path=" + encodeURIComponent(p) + fullDataParams() + "&report_all_tags=1";
    if (skipCache) url += "&_=" + Date.now();
    return fetchJson(url)
      .then(function (data) {
        var allEntries = data.entries || [];
        var viewData = { type: "listing", path: p, entries: allEntries };
        if (pane === "left") lastViewDataLeft = viewData; else lastViewDataRight = viewData;
        lastViewData = viewData;
        var visible = filterEntriesByVisibility(allEntries, p);
        tagsInCurrentView = tagsInScopeFromEntries(visible);
        refreshTagsSection();
        renderListingFromEntries(visible, p, listEl, pane);
        if (savedScroll != null) listEl.scrollTop = savedScroll;
        refreshChangesPane();
        saveStateDebounced();
      })
      .catch(function (err) {
        listEl.innerHTML = '<div class="error">' + escapeHtml(err.message || "Failed to load") + "</div>";
        if (pane === "left" && currentPathLeft && roots.length) {
          currentPathLeft = null;
          currentPath = currentPathRight;
          if (currentPathLeftEl) currentPathLeftEl.textContent = "";
          saveStateDebounced();
        } else if (pane === "right" && currentPathRight && roots.length) {
          currentPathRight = null;
          if (currentPathRightEl) currentPathRightEl.textContent = "";
          saveStateDebounced();
        }
      });
  }

  function escapeHtml(s) {
    if (s == null) return "";
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  function formatSize(bytes, isDir) {
    if (isDir) return "—";
    if (bytes == null || bytes === 0) return "0 B";
    const units = ["B", "KB", "MB", "GB", "TB"];
    let u = 0;
    let n = Number(bytes);
    while (n >= 1024 && u < units.length - 1) {
      n /= 1024;
      u += 1;
    }
    return (u === 0 ? n : n.toFixed(1)) + " " + units[u];
  }

  function updateSelectionBar() {
    if (!selectionBarEl || !selectionCountEl) return;
    const n = selectedPaths.size;
    if (n === 0) {
      selectionBarEl.classList.remove("visible");
      return;
    }
    selectionBarEl.classList.add("visible");
    selectionCountEl.textContent = n + " selected";
    if (batchTagInputEl) batchTagInputEl.value = "";
  }

  function clearSelection() {
    selectedPaths.clear();
    updateSelectionBar();
    if (currentTag) { if (isTagSearchView) doTagSearch(currentTag); else navigateToTag(currentTag); } else {
      if (currentPathLeft) navigateTo(currentPathLeft, "left"); else navigateTo(roots[0], "left");
      if (currentPathRight) navigateTo(currentPathRight, "right"); else navigateTo(roots[0], "right");
    }
  }

  function addTagBatch() {
    if (!batchTagInputEl || selectedPaths.size === 0) return;
    const tag = batchTagInputEl.value.trim();
    if (!tag) return;
    fetch(api("tags/batch"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ paths: Array.from(selectedPaths), tag: tag }),
    })
      .then(function (r) { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then(function (data) {
        selectedPaths.clear();
        updateSelectionBar();
        refreshTagsSection();
        if (currentTag) { if (isTagSearchView) doTagSearch(currentTag); else navigateToTag(currentTag); } else {
          if (currentPathLeft) navigateTo(currentPathLeft, "left"); else navigateTo(roots[0], "left");
          if (currentPathRight) navigateTo(currentPathRight, "right"); else navigateTo(roots[0], "right");
        }
      })
      .catch(function (err) { alert(err.message || "Failed to add tag"); });
  }

  function addTag(path, tag, inputEl, afterRefresh) {
    fetch(api("tags"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: path, tag: tag }),
    })
      .then(function (r) { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then(function () {
        if (inputEl) inputEl.value = "";
        refreshTagsSection();
        var p;
        if (currentTag) {
          if (isTagSearchView) { doTagSearch(currentTag); p = null; }
          else p = navigateToTag(currentTag);
        } else {
          p = Promise.all([
            navigateTo(currentPathLeft || "/", "left", true),
            navigateTo(currentPathRight || "/", "right", true),
          ]);
        }
        if (p && typeof p.then === "function" && afterRefresh) p.then(afterRefresh);
        else if (afterRefresh) setTimeout(afterRefresh, 0);
      })
      .catch(function (err) { alert(err.message || "Failed to add tag"); });
  }

  function removeTag(path, tag) {
    fetch(api("tags") + "?path=" + encodeURIComponent(path) + "&tag=" + encodeURIComponent(tag), { method: "DELETE" })
      .then(function (r) { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then(function () {
        if (currentTag) {
          refreshTagsSection();
          if (isTagSearchView) doTagSearch(currentTag); else navigateToTag(currentTag);
        } else {
          if (currentPathLeft) navigateTo(currentPathLeft, "left", true); else navigateTo(roots[0], "left");
          if (currentPathRight) navigateTo(currentPathRight, "right", true); else navigateTo(roots[0], "right");
        }
      })
      .catch(function (err) { alert(err.message || "Failed to remove tag"); });
  }

  function flipToNull(path, tag) {
    fetch(api("tag-nulls"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: path, tag: tag }),
    })
      .then(function (r) { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then(function () {
        refreshTagsSection();
        if (currentTag) { if (isTagSearchView) doTagSearch(currentTag); else navigateToTag(currentTag); } else {
          if (currentPathLeft) navigateTo(currentPathLeft, "left", true); else navigateTo(roots[0], "left");
          if (currentPathRight) navigateTo(currentPathRight, "right", true); else navigateTo(roots[0], "right");
        }
      })
      .catch(function (err) { alert(err.message || "Failed to set null tag"); });
  }

  function flipNullToHard(path, tag) {
    fetch(api("tag-nulls") + "?path=" + encodeURIComponent(path) + "&tag=" + encodeURIComponent(tag), { method: "DELETE" })
      .then(function (r) { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then(function () {
        refreshTagsSection();
        if (currentTag) { if (isTagSearchView) doTagSearch(currentTag); else navigateToTag(currentTag); } else {
          if (currentPathLeft) navigateTo(currentPathLeft, "left", true); else navigateTo(roots[0], "left");
          if (currentPathRight) navigateTo(currentPathRight, "right", true); else navigateTo(roots[0], "right");
        }
      })
      .catch(function (err) { alert(err.message || "Failed to make hard tag"); });
  }

  /* Delegated handlers so trash and tagging work the same for every row (including empty). */
  function attachListingHandlers(listEl, pane) {
    if (!listEl) return;
    listEl.addEventListener("dblclick", function (e) {
      var el = e.target && e.target.nodeType === 1 ? e.target : (e.target && e.target.parentElement);
      if (el && el.closest && el.closest(".name-cell-text")) {
        if (pendingRenameTimeout) {
          clearTimeout(pendingRenameTimeout);
          pendingRenameTimeout = null;
        }
      }
    }, true);
    listEl.addEventListener("click", function (e) {
      var el = e.target && e.target.nodeType === 1 ? e.target : (e.target && e.target.parentElement);
      if (!el || !el.closest) return;
      var nameEl = el.closest(".name-cell-text");
      if (nameEl) {
        var row = nameEl.closest("tr");
        if (row && row.dataset.path && row.classList.contains("row-selected") && !row.querySelector("input.rename-input") && e.detail === 1) {
          e.preventDefault();
          e.stopPropagation();
          if (pendingRenameTimeout) clearTimeout(pendingRenameTimeout);
          pendingRenameTimeout = setTimeout(function () {
            pendingRenameTimeout = null;
            startInlineRename(row, pane);
          }, 250);
        }
        return;
      }
    }, true);
    listEl.addEventListener("click", function (e) {
      var el = e.target && e.target.nodeType === 1 ? e.target : (e.target && e.target.parentElement);
      if (!el || !el.closest) return;
      var row = el.closest("tr[data-path]");
      if (row && !el.closest(".tags-cell") && !el.closest(".checkbox-cell") && !el.closest(".actions-cell") && !el.closest(".name-cell-text") && !el.closest("input.rename-input")) {
        var renameInput = row.querySelector(".name-cell input.rename-input");
        if (renameInput) {
          e.preventDefault();
          e.stopPropagation();
          abortRenameInRow(row);
        }
      }
      var removeBtn = el.closest(".tag-remove");
      if (removeBtn && removeBtn.dataset.path) {
        e.preventDefault();
        e.stopPropagation();
        removeTag(removeBtn.dataset.path, removeBtn.dataset.tag);
        return;
      }
      if (!currentTag) {
        activePane = pane;
        setCurrentPath(pane === "left" ? currentPathLeft : currentPathRight, pane);
      }
      el = e.target && e.target.nodeType === 1 ? e.target : (e.target && e.target.parentElement);
      if (!el || !el.closest) return;
      var btn = el.closest(".btn-trash");
      if (btn && !btn.disabled && btn.dataset.path) {
        e.preventDefault();
        e.stopPropagation();
        var row = btn.closest("tr");
        var path = btn.dataset.path;
        var displayPath = (row && row.dataset.vpath) ? row.dataset.vpath : path;
        var newVpath = "__VTRASH/" + (displayPath.charAt(0) === "/" ? displayPath.slice(1) : displayPath);
        if (newVpath === "__VTRASH/") newVpath = "__VTRASH/" + path;
        fetch(api("move"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: path, vpath: newVpath }),
        })
          .then(function (r) {
            if (!r.ok) return r.json().then(function (d) {
            var msg = (d.error && d.error.message) || d.error || r.statusText;
            throw new Error(typeof msg === "string" ? msg : "Request failed");
          });
            return r.json();
          })
          .then(function () {
            refreshAfterMoveOrRestore();
          })
          .catch(function (err) { alert(err.message || "Move failed"); });
        return;
      }
      var restoreBtn = el.closest(".btn-restore");
      if (restoreBtn && restoreBtn.dataset.path) {
        e.preventDefault();
        e.stopPropagation();
        var path = restoreBtn.dataset.path;
        fetch(api("move"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: path, vpath: "" }),
        })
          .then(function (r) {
            if (!r.ok) return r.json().then(function (d) {
            var msg = (d.error && d.error.message) || d.error || r.statusText;
            throw new Error(typeof msg === "string" ? msg : "Request failed");
          });
            return r.json();
          })
          .then(function () {
            refreshAfterMoveOrRestore();
          })
          .catch(function (err) { alert(err.message || "Restore failed"); });
        return;
      }
      var pill = el.closest(".tag-pill-hard");
      if (pill && !el.closest(".tag-remove")) {
        e.preventDefault();
        e.stopPropagation();
        flipToNull(pill.dataset.path, pill.dataset.tag);
        return;
      }
      pill = el.closest(".tag-pill-soft");
      if (pill) {
        e.preventDefault();
        e.stopPropagation();
        addTag(pill.dataset.path, pill.dataset.tag, null);
        return;
      }
      pill = el.closest(".tag-pill-null");
      if (pill) {
        e.preventDefault();
        e.stopPropagation();
        flipNullToHard(pill.dataset.path, pill.dataset.tag);
        return;
      }
    });
    listEl.addEventListener("keydown", function (e) {
      var el = e.target && e.target.nodeType === 1 ? e.target : (e.target && e.target.parentElement);
      if (!el || !el.closest) return;
      var input = el.closest(".tag-input");
      if (input && e.key === "Enter") {
        if (input.classList.contains("rule-row-tag-input") || input.classList.contains("rule-tag-input")) return;
        e.preventDefault();
        var tag = input.value.trim();
        if (tag) addTag(input.dataset.path, tag, input);
        return;
      }
      var pill = el.closest(".tag-pill-hard, .tag-pill-soft, .tag-pill-null");
      if (pill && !el.closest(".tag-remove") && (e.key === "Enter" || e.key === " ")) {
        e.preventDefault();
        e.stopPropagation();
        if (pill.classList.contains("tag-pill-null")) flipNullToHard(pill.dataset.path, pill.dataset.tag);
        else if (pill.classList.contains("tag-pill-soft")) addTag(pill.dataset.path, pill.dataset.tag, null);
        else flipToNull(pill.dataset.path, pill.dataset.tag);
      }
    });
  }
  attachListingHandlers(listingLeftEl, "left");
  attachListingHandlers(listingRightEl, "right");

  function attachDragDrop(listEl, pane) {
    if (!listEl) return;
    var dragImageEl = null;
    var draggedPath = null;
    function makeDragImage(isDir) {
      var el = document.createElement("div");
      el.className = "drag-image-icon";
      el.textContent = isDir ? "\uD83D\uDCC1" : "\uD83D\uDCC4";
      el.setAttribute("aria-hidden", "true");
      document.body.appendChild(el);
      return el;
    }
    function isSelfOrDescendant(dragPath, targetPath) {
      if (!dragPath || !targetPath) return false;
      if (dragPath === targetPath) return true;
      var sep = targetPath.startsWith(dragPath + "/") || targetPath.startsWith(dragPath + "\\");
      return targetPath.length > dragPath.length && sep;
    }
    listEl.addEventListener("dragstart", function (e) {
      var row = e.target.closest("tr[data-path]");
      if (!row) return;
      var path = row.dataset.path;
      draggedPath = path;
      draggedFromPane = pane || (listEl === listingLeftEl ? "left" : "right");
      var isDir = row.dataset.isdir === "true" || row.dataset.isdir === "True";
      e.dataTransfer.setData("text/plain", path);
      e.dataTransfer.effectAllowed = "move";
      dragImageEl = makeDragImage(isDir);
      e.dataTransfer.setDragImage(dragImageEl, 20, 20);
    });
    listEl.addEventListener("dragend", function () {
      draggedPath = null;
      draggedFromPane = null;
      listEl.querySelectorAll("tr.drag-target").forEach(function (r) { r.classList.remove("drag-target"); });
      if (dragImageEl && dragImageEl.parentNode) dragImageEl.parentNode.removeChild(dragImageEl);
      dragImageEl = null;
    });
    listEl.addEventListener("dragover", function (e) {
      var row = e.target.closest("tr[data-path]");
      listEl.querySelectorAll("tr.drag-target").forEach(function (r) { r.classList.remove("drag-target"); });
      if (row && row.dataset.isdir === "true") {
        var targetPath = row.dataset.path;
        if (targetPath && isSelfOrDescendant(draggedPath, targetPath)) {
          e.dataTransfer.dropEffect = "none";
          return;
        }
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        row.classList.add("drag-target");
      }
    });
    listEl.addEventListener("dragleave", function (e) {
      if (!e.target.closest || !e.target.closest("tr[data-path]") || !listEl.contains(e.relatedTarget)) {
        listEl.querySelectorAll("tr.drag-target").forEach(function (r) { r.classList.remove("drag-target"); });
      }
    });
    listEl.addEventListener("drop", function (e) {
      var row = e.target.closest("tr[data-path]");
      listEl.querySelectorAll("tr.drag-target").forEach(function (r) { r.classList.remove("drag-target"); });
      if (!row || row.dataset.isdir !== "true") return;
      e.preventDefault();
      var path = e.dataTransfer.getData("text/plain");
      if (!path) return;
      var targetPath = row.dataset.path;
      if (!targetPath) return;
      if (isSelfOrDescendant(path, targetPath)) return;
      var targetVpath = row.dataset.vpath || targetPath;
      var name = path.split("/").pop() || path.split("\\\\").pop() || path;
      var vpath = (targetVpath === "/" || !targetVpath) ? "/" + name : targetVpath + "/" + name;
      fetch(api("move"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: path, vpath: vpath }),
      })
        .then(function (r) {
          if (!r.ok) return r.json().then(function (d) {
            var msg = (d.error && d.error.message) || d.error || r.statusText;
            throw new Error(typeof msg === "string" ? msg : "Request failed");
          });
          return r.json();
        })
        .then(function () {
          if (currentTag && draggedFromPane === "left") {
            return fetch(api("tags") + "?path=" + encodeURIComponent(path) + "&tag=" + encodeURIComponent(currentTag), { method: "DELETE" })
              .then(function (r) { if (!r.ok) throw new Error(r.statusText); return r.json(); })
              .then(function () {});
          }
        })
        .then(function () {
          refreshAfterMoveOrRestore();
        })
        .catch(function (err) { alert(err.message || "Move failed"); });
    });
  }
  attachDragDrop(listingLeftEl, "left");
  attachDragDrop(listingRightEl, "right");

  function attachDropzone(dropzoneEl, pane) {
    if (!dropzoneEl) return;
    dropzoneEl.addEventListener("dragover", function (e) {
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      dropzoneEl.classList.add("drag-over");
    });
    dropzoneEl.addEventListener("dragleave", function () {
      dropzoneEl.classList.remove("drag-over");
    });
    dropzoneEl.addEventListener("drop", function (e) {
      e.preventDefault();
      dropzoneEl.classList.remove("drag-over");
      var path = e.dataTransfer.getData("text/plain");
      if (!path) return;
      if (pane === "left" && isTagSearchView) return;
      if (pane === "left" && currentTag && !isTagSearchView) {
        fetch(api("tags/batch"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ paths: [path], tag: currentTag }),
        })
          .then(function (r) {
            if (!r.ok) return r.json().then(function (d) {
              var msg = (d.error && d.error.message) || d.error || r.statusText;
              throw new Error(typeof msg === "string" ? msg : "Request failed");
            });
            return r.json();
          })
          .then(function () {
            refreshTagsSection();
            if (currentTag) { if (isTagSearchView) doTagSearch(currentTag); else navigateToTag(currentTag); }
            refreshPaneListing("right");
          })
          .catch(function (err) { alert(err.message || "Failed to add tag"); });
        return;
      }
      var scope = pane === "left" ? currentPathLeft : currentPathRight;
      if (!scope) scope = roots.length ? roots[0] : "/";
      if (typeof scope !== "string") scope = String(scope);
      if (path === scope) return;
      if (scope.length > path.length && (scope.startsWith(path + "/") || scope.startsWith(path + "\\"))) return;
      var name = path.split("/").pop() || path.split("\\\\").pop() || path;
      var vpath = (scope === "/" || !scope) ? "/" + name : scope.replace(/\/$/, "") + "/" + name;
      fetch(api("move"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: path, vpath: vpath }),
      })
        .then(function (r) {
          if (!r.ok) return r.json().then(function (d) {
            var msg = (d.error && d.error.message) || d.error || r.statusText;
            throw new Error(typeof msg === "string" ? msg : "Request failed");
          });
          return r.json();
        })
        .then(function () {
          if (currentTag && draggedFromPane === "left") {
            return fetch(api("tags") + "?path=" + encodeURIComponent(path) + "&tag=" + encodeURIComponent(currentTag), { method: "DELETE" })
              .then(function (r) { if (!r.ok) throw new Error(r.statusText); return r.json(); })
              .then(function () {});
          }
        })
        .then(function () {
          refreshAfterMoveOrRestore();
        })
        .catch(function (err) { alert(err.message || "Move failed"); });
    });
  }
  attachDropzone(dropzoneLeftEl, "left");
  attachDropzone(dropzoneRightEl, "right");
  updateDropzoneLabels();

  document.addEventListener("keydown", function (e) {
      var active = document.activeElement;
      if (active && (active.tagName === "INPUT" || active.tagName === "TEXTAREA" || active.tagName === "SELECT" || active.isContentEditable)) return;
      var selected = (listingLeftEl && listingLeftEl.querySelector("tr.row-selected")) || (listingRightEl && listingRightEl.querySelector("tr.row-selected"));
      var listEl = null;
      var pane = "left";
      if (listingLeftEl && selected && listingLeftEl.contains(selected)) { listEl = listingLeftEl; pane = "left"; }
      else if (listingRightEl && selected && listingRightEl.contains(selected)) { listEl = listingRightEl; pane = "right"; }
      if (!listEl) listEl = listingLeftEl;
      var rows = listEl ? listEl.querySelectorAll("tbody tr[data-path]") : [];
      if (!rows.length) return;
      if (!selected) selected = listEl.querySelector("tr.row-selected");
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        var idx = -1;
        for (var i = 0; i < rows.length; i++) { if (rows[i] === selected) { idx = i; break; } }
        if (idx < 0) return;
        var nextIdx = e.key === "ArrowDown" ? idx + 1 : idx - 1;
        if (nextIdx < 0 || nextIdx >= rows.length) return;
        e.preventDefault();
        if (currentTag || isTagSearchView) {
          selectListingRow(rows[nextIdx], pane);
          rows[nextIdx].scrollIntoView({ block: "nearest" });
        } else {
          activateListingRow(rows[nextIdx], pane);
          rows[nextIdx].scrollIntoView({ block: "nearest" });
        }
        return;
      }
      if (e.key === "Backspace" && selected && selected.dataset && selected.dataset.path) {
        var trashBtn = selected.querySelector(".btn-trash");
        if (trashBtn && !trashBtn.disabled) {
          e.preventDefault();
          var idx = -1;
          for (var i = 0; i < rows.length; i++) { if (rows[i] === selected) { idx = i; break; } }
          var pathToSelect = null;
          if (idx > 0) pathToSelect = rows[idx - 1].getAttribute("data-path");
          else if (idx === 0 && rows.length > 1) pathToSelect = rows[1].getAttribute("data-path");
          var path = selected.dataset.path;
          var displayPath = selected.dataset.vpath || path;
          var newVpath = "__VTRASH/" + (displayPath.charAt(0) === "/" ? displayPath.slice(1) : displayPath);
          if (newVpath === "__VTRASH/") newVpath = "__VTRASH/" + path;
          fetch(api("move"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ path: path, vpath: newVpath }),
          })
            .then(function (r) {
              if (!r.ok) return r.json().then(function (d) {
            var msg = (d.error && d.error.message) || d.error || r.statusText;
            throw new Error(typeof msg === "string" ? msg : "Request failed");
          });
              return r.json();
            })
            .then(function () {
              refreshAfterMoveOrRestore();
            })
            .then(function () {
              if (pathToSelect) selectRowByPath(pathToSelect);
            })
            .catch(function (err) { alert(err.message || "Move failed"); });
        }
      }
    });

  if (btnUpLeft) {
    btnUpLeft.addEventListener("click", function () {
    if (btnUpLeft.disabled) return;
    if (showRulesView) {
      showRulesView = false;
      refreshTree();
      if (currentPathLeft) navigateTo(currentPathLeft, "left"); else navigateTo(roots[0], "left");
      if (currentPathRight) navigateTo(currentPathRight, "right"); else navigateTo(roots[0], "right");
      return;
    }
    if (currentTag) {
      clearTagView();
      return;
    }
    fetchJson("parent?path=" + encodeURIComponent(currentPathLeft))
      .then(function (data) {
        if (data.parent != null) navigateTo(data.parent, "left");
      });
  });
  }
  if (btnUpRight) {
    btnUpRight.addEventListener("click", function () {
    if (btnUpRight.disabled) return;
    if (showRulesView) {
      showRulesView = false;
      refreshTree();
      if (currentPathLeft) navigateTo(currentPathLeft, "left"); else navigateTo(roots[0], "left");
      if (currentPathRight) navigateTo(currentPathRight, "right"); else navigateTo(roots[0], "right");
      return;
    }
    fetchJson("parent?path=" + encodeURIComponent(currentPathRight))
      .then(function (data) {
        if (data.parent != null) navigateTo(data.parent, "right");
      });
  });
  }

  if (btnAddFolderLeftEl) {
    btnAddFolderLeftEl.addEventListener("click", function () {
      if (currentTag || !currentPathLeft) return;
      var name = (typeof prompt === "function" ? prompt("Folder name") : null) || "";
      name = name.trim();
      if (!name) return;
      fetch(api("new-folder"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: currentPathLeft, name: name }),
      })
        .then(function (r) {
          if (!r.ok) return r.json().then(function (d) {
            var msg = (d.error && d.error.message) || d.error || r.statusText;
            throw new Error(typeof msg === "string" ? msg : "Request failed");
          });
          return r.json();
        })
        .then(function () {
          navigateTo(currentPathLeft, "left");
          if ((currentPathLeft || "").replace(/\/$/, "") === "/Volumes") refreshTree();
        })
        .catch(function (err) {
          alert(err.message || "Failed to create folder");
        });
    });
  }
  if (btnAddFolderRightEl) {
    btnAddFolderRightEl.addEventListener("click", function () {
      if (!currentPathRight) return;
      var name = (typeof prompt === "function" ? prompt("Folder name") : null) || "";
      name = name.trim();
      if (!name) return;
      fetch(api("new-folder"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: currentPathRight, name: name }),
      })
        .then(function (r) {
          if (!r.ok) return r.json().then(function (d) {
            var msg = (d.error && d.error.message) || d.error || r.statusText;
            throw new Error(typeof msg === "string" ? msg : "Request failed");
          });
          return r.json();
        })
        .then(function () {
          if (currentTag) refreshPaneListing("right");
          else navigateTo(currentPathRight, "right");
          if ((currentPathRight || "").replace(/\/$/, "") === "/Volumes") refreshTree();
        })
        .catch(function (err) {
          alert(err.message || "Failed to create folder");
        });
    });
  }

  if (btnBatchTagEl) {
    btnBatchTagEl.addEventListener("click", addTagBatch);
  }
  if (batchTagInputEl) {
    batchTagInputEl.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { e.preventDefault(); addTagBatch(); }
    });
  }
  if (btnClearSelectionEl) {
    btnClearSelectionEl.addEventListener("click", clearSelection);
  }

  if (hideTrashCheckboxEl) {
    showTrashed = !!hideTrashCheckboxEl.checked;
    hideTrashCheckboxEl.addEventListener("change", function () {
      showTrashed = hideTrashCheckboxEl.checked;
      refreshCurrentView();
      saveStateDebounced();
    });
  }

  if (showNullTagsCheckboxEl) {
    showNullTags = !!showNullTagsCheckboxEl.checked;
    showNullTagsCheckboxEl.addEventListener("change", function () {
      showNullTags = showNullTagsCheckboxEl.checked;
      if (currentTag) {
        if (isTagSearchView) doTagSearch(currentTag);
        else navigateToTag(currentTag);
      }
      saveStateDebounced();
    });
  }

  if (previewBodyEl) {
    previewBodyEl.addEventListener("click", function () {
      if (previewPaneCollapsed) return;
      if (previewSelectedPath) {
        loadPreviewForPath(previewSelectedPath);
      }
    });
  }

  if (previewToggleEl && previewPaneEl) {
    previewToggleEl.addEventListener("click", function () {
      previewPaneCollapsed = !previewPaneCollapsed;
      previewPaneEl.classList.toggle("collapsed", previewPaneCollapsed);
      if (previewPaneCollapsed) {
        if (previewBodyEl) previewBodyEl.innerHTML = "";
        if (previewFooterEl) previewFooterEl.textContent = "";
        previewToggleEl.textContent = "◀";
        previewToggleEl.title = "Expand preview";
        previewToggleEl.setAttribute("aria-label", "Expand preview");
      } else {
        previewToggleEl.textContent = "▶";
        previewToggleEl.title = "Collapse preview";
        previewToggleEl.setAttribute("aria-label", "Collapse preview");
        if (previewSelectedPath) loadPreviewForPath(previewSelectedPath);
      }
      saveStateDebounced();
    });
  }

  fetchJson("roots")
    .then(function (r) {
      roots = r || [];
      if (roots.length) {
        var state = getPersistedState();
        applyPersistedState(state);
        currentPath = currentPathLeft || currentPath;
        if (hideTrashCheckboxEl) hideTrashCheckboxEl.checked = showTrashed;
        if (showNullTagsCheckboxEl) showNullTagsCheckboxEl.checked = showNullTags;
        if (previewPaneEl) {
          previewPaneEl.classList.toggle("collapsed", previewPaneCollapsed);
          if (previewToggleEl) {
            if (previewPaneCollapsed) {
              previewToggleEl.textContent = "◀";
              previewToggleEl.title = "Expand preview";
              previewToggleEl.setAttribute("aria-label", "Expand preview");
            } else {
              previewToggleEl.textContent = "▶";
              previewToggleEl.title = "Collapse preview";
              previewToggleEl.setAttribute("aria-label", "Collapse preview");
            }
          }
        }
        setCurrentPath(currentPathLeft || currentPath || roots[0], "left");
        setCurrentPath(currentPathRight || currentPath || roots[0], "right");
        refreshTree();
        if (currentTag) {
          if (isTagSearchView) doTagSearch(currentTag);
          else navigateToTag(currentTag);
        } else {
          navigateTo(currentPathLeft || roots[0], "left");
          navigateTo(currentPathRight || roots[0], "right");
        }
      } else {
        listingLeftEl.innerHTML = '<div class="error">No roots available</div>';
        if (listingRightEl) listingRightEl.innerHTML = "";
      }
    })
    .catch(function (err) {
      listingLeftEl.innerHTML = '<div class="error">' + escapeHtml(err.message) + "</div>";
      if (listingRightEl) listingRightEl.innerHTML = "";
    });

  var searchWrapEl = document.getElementById("searchWrap");
  if (searchWrapEl) addTagsSearchInputTo(searchWrapEl);
})();
