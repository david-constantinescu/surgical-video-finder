(() => {
  const LANG_KEY = "svf_lang";
  const SELECTED_KEY = "svf_selected";
  let lang = localStorage.getItem(LANG_KEY) || window.APP_LANG || "en";
  let i18n = {};
  let selected = new Map();
  let searchTimer = null;
  let resultIndex = -1;
  let lastResults = [];

  const $ = (sel) => document.querySelector(sel);

  function loadSelected() {
    try {
      const raw = localStorage.getItem(SELECTED_KEY);
      if (raw) {
        const arr = JSON.parse(raw);
        arr.forEach((t) => selected.set(t.id, t));
      }
    } catch { /* ignore */ }
  }

  function saveSelected() {
    localStorage.setItem(SELECTED_KEY, JSON.stringify(Array.from(selected.values())));
  }

  async function loadI18n() {
    const res = await fetch(`/api/i18n/${lang}`);
    i18n = await res.json();
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      if (i18n[key]) el.textContent = i18n[key];
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      const key = el.getAttribute("data-i18n-placeholder");
      if (i18n[key]) el.placeholder = i18n[key];
    });
    document.querySelectorAll(".lang-btn").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.lang === lang);
    });
  }

  function t(key) {
    return i18n[key] || key;
  }

  function truncate(str, max = 48) {
    if (str.length <= max) return str;
    return `${str.slice(0, max - 1)}…`;
  }

  function renderSelected() {
    const chips = $("#selectedChips");
    const empty = $("#selectedEmpty");
    const btn = $("#findVideosBtn");
    const panel = $("#selectedPanel");
    chips.innerHTML = "";

    if (selected.size === 0) {
      empty.style.display = "block";
      btn.disabled = true;
      $("#clearSelectedBtn").disabled = true;
      return;
    }
    empty.style.display = "none";
    btn.disabled = false;
    $("#clearSelectedBtn").disabled = false;

    selected.forEach((term) => {
      const chip = document.createElement("span");
      chip.className = "chip";
      const badge = term.fallback_en
        ? ` [${t("results.fallbackEn")}]`
        : term.fallback_ro
          ? ` [${t("results.fallbackRo")}]`
          : "";
      chip.innerHTML = `
        <span title="${escapeHtml(term.display_name)}">${escapeHtml(truncate(term.display_name))}${badge}</span>
        <button type="button" aria-label="${t("selected.remove")}" data-id="${term.id}">&times;</button>
      `;
      chip.querySelector("button").addEventListener("click", () => {
        selected.delete(term.id);
        saveSelected();
        renderSelected();
      });
      chips.appendChild(chip);
    });
    panel.classList.add("highlight");
    setTimeout(() => panel.classList.remove("highlight"), 1200);
  }

  function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  function renderExamples() {
    const container = $("#searchResults");
    container.innerHTML = `
      <p class="empty-msg">${t("search.examplesTitle")}</p>
      <div class="suggestions">
        ${(i18n["search.suggestions"] || "").split("|").map((s) =>
          `<button type="button" class="suggestion-btn">${escapeHtml(s.trim())}</button>`
        ).join("")}
      </div>
    `;
    container.querySelectorAll(".suggestion-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        $("#searchInput").value = btn.textContent;
        doSearch();
      });
    });
  }

  function renderNoResults() {
    const container = $("#searchResults");
    container.innerHTML = `
      <p class="empty-msg">${t("search.noResultsTry")}</p>
      <div class="suggestions">
        ${(i18n["search.suggestions"] || "").split("|").map((s) =>
          `<button type="button" class="suggestion-btn">${escapeHtml(s.trim())}</button>`
        ).join("")}
      </div>
    `;
    container.querySelectorAll(".suggestion-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        $("#searchInput").value = btn.textContent;
        doSearch();
      });
    });
  }

  async function doSearch() {
    const q = $("#searchInput").value.trim();
    const container = $("#searchResults");
    const countEl = $("#searchCount");
    if (!q) {
      container.innerHTML = "";
      countEl.textContent = "";
      lastResults = [];
      return;
    }
    countEl.textContent = "";
    container.innerHTML = `<p class="empty-msg loading"><span class="spinner"></span> ${t("search.loading")}</p>`;
    const mode = $("#searchMode").value;
    const kind = $("#kindFilter").value;
    const params = new URLSearchParams({ q, lang, mode, limit: "20" });
    if (kind) params.set("kind", kind);

    try {
      const res = await fetch(`/api/terms/search?${params}`);
      const data = await res.json();
      if (res.status === 503 && data.error === "semantic_index_missing") {
        container.innerHTML = `<p class="empty-msg">${t("search.semanticMissing")}</p>`;
        return;
      }
      lastResults = data.results || [];
      resultIndex = -1;
      if (!lastResults.length) {
        renderNoResults();
        return;
      }
      countEl.textContent = t("search.resultCount").replace("{n}", data.count);
      container.innerHTML = lastResults.map((term, i) => renderResult(term, i)).join("");
      bindResultHandlers();
    } catch {
      container.innerHTML = `<p class="empty-msg">${t("error.generic")}</p>`;
    }
  }

  function bindResultHandlers() {
    const container = $("#searchResults");
    container.querySelectorAll(".add-btn").forEach((btn) => {
      btn.addEventListener("click", () => addTerm(Number(btn.dataset.id)));
    });
    container.querySelectorAll(".result-item").forEach((el) => {
      el.addEventListener("mouseenter", () => {
        resultIndex = Number(el.dataset.index);
        highlightResult();
      });
    });
  }

  function addTerm(id) {
    const term = lastResults.find((r) => r.id === id);
    if (!term) return;
    selected.set(id, term);
    saveSelected();
    renderSelected();
    doSearch();
    $("#selectedPanel").scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function renderResult(term, index) {
    const kindLabel = term.kind === "procedure" ? t("results.kind.procedure") : t("results.kind.diagnosis");
    const layerLabel = term.layer === "curated" ? t("results.layer.curated") : t("results.layer.comprehensive");
    const code = term.code
      ? `<span class="tag">${t("results.code")}: ${escapeHtml(term.code)}${term.code_system ? ` (${escapeHtml(term.code_system)})` : ""}</span>`
      : "";
    const enBadge = term.fallback_en ? `<span class="tag en-fallback">${t("results.fallbackEn")}</span>` : "";
    const roBadge = term.fallback_ro ? `<span class="tag ro-fallback">${t("results.fallbackRo")}</span>` : "";

    return `
      <div class="result-item" data-index="${index}" role="option">
        <div class="result-meta">
          <div class="result-name" title="${escapeHtml(term.display_name)}">${escapeHtml(term.display_name)}</div>
          <div class="result-tags">
            <span class="tag">${kindLabel}</span>
            <span class="tag">${layerLabel}</span>
            ${code}${enBadge}${roBadge}
          </div>
        </div>
        <button type="button" class="add-btn" data-id="${term.id}" ${selected.has(term.id) ? "disabled" : ""}>
          ${t("results.add")}
        </button>
      </div>
    `;
  }

  function highlightResult() {
    document.querySelectorAll(".result-item").forEach((el, i) => {
      el.classList.toggle("active", i === resultIndex);
    });
  }

  async function findVideos(forceRefresh = false) {
    const container = $("#videoLinks");
    const empty = $("#videosEmpty");
    if (selected.size === 0) return;

    empty.style.display = "none";
    container.innerHTML = `<p class="empty-msg loading"><span class="spinner"></span> ${t("videos.loading")}</p>`;

    const ids = Array.from(selected.keys()).join(",");
    const refreshParam = forceRefresh ? "&refresh=1" : "";
    try {
      const res = await fetch(`/api/videos/links?term_ids=${ids}&lang=${lang}${refreshParam}`);
      const data = await res.json();
      const groups = data.groups || [];
      if (!groups.length) {
        container.innerHTML = `<p class="empty-msg">${t("videos.empty")}</p>`;
        return;
      }
      container.innerHTML = groups.map((grp) => `
        <section class="video-group">
          <h3 class="video-group-title">${escapeHtml(grp.term_name)}</h3>
          ${renderInlineVideos(grp.inline_videos || [])}
          ${(grp.sources || []).length ? `<h4 class="video-subheading">${t("videos.moreSources")}</h4>` : ""}
          ${(grp.sources || []).map((src) => renderVideoLink(src)).join("")}
        </section>
      `).join("");
      bindInlineVideoHandlers();
      $("#refreshVideosBtn").hidden = false;
    } catch {
      container.innerHTML = `<p class="empty-msg">${t("error.generic")}</p>`;
    }
  }

  function renderInlineVideos(videos) {
    if (!videos.length) return "";
    const bySource = videos.reduce((acc, video) => {
      const key = video.source || "other";
      if (!acc[key]) acc[key] = [];
      acc[key].push(video);
      return acc;
    }, {});

    const order = ["youtube", "vimeo", "pubmed"];
    const sections = order.filter((k) => bySource[k]?.length);
    Object.keys(bySource).forEach((k) => {
      if (!sections.includes(k)) sections.push(k);
    });

    return `
      <h4 class="video-subheading">${t("videos.inlineTitle")}</h4>
      ${sections.map((source) => `
        <h5 class="video-source-heading">${t(`videos.source.${source}`) || source}</h5>
        <div class="video-thumb-grid">
          ${bySource[source].map((video) => renderInlineCard(video)).join("")}
        </div>
      `).join("")}
    `;
  }

  function renderInlineCard(video) {
    const isArticle = video.media_type === "article";
    const thumb = video.thumbnail_url
      ? `<img class="video-card-thumb" src="${escapeHtml(video.thumbnail_url)}" alt="" loading="lazy">`
      : `<div class="video-card-thumb video-card-thumb--empty ${isArticle ? "video-card-thumb--article" : ""}">
           <span class="video-card-icon">${isArticle ? "📄" : "▶"}</span>
         </div>`;
    const action = isArticle
      ? `<a class="video-card-action" href="${video.url}" target="_blank" rel="noopener noreferrer">${t("videos.read")}</a>`
      : (video.embed_url
        ? `<button type="button" class="video-card-action" data-embed-play
            data-embed-url="${escapeHtml(video.embed_url)}"
            data-external-url="${escapeHtml(video.url)}"
            data-embed-title="${escapeHtml(video.title)}">${t("videos.play")}</button>`
        : `<a class="video-card-action" href="${video.url}" target="_blank" rel="noopener noreferrer">${t("videos.open")}</a>`);

    return `
      <article class="video-card">
        ${thumb}
        <div class="video-card-body">
          <div class="video-card-title" title="${escapeHtml(video.title)}">${escapeHtml(truncate(video.title, 64))}</div>
          ${video.channel ? `<div class="video-card-channel">${escapeHtml(video.channel)}</div>` : ""}
          ${video.cached ? `<div class="video-card-cache">${t("videos.cached")}</div>` : ""}
          <div class="video-card-actions">${action}</div>
        </div>
      </article>
    `;
  }

  function bindInlineVideoHandlers() {
    document.querySelectorAll("[data-embed-play]").forEach((btn) => {
      btn.addEventListener("click", () => {
        openEmbedModal(btn.dataset.embedUrl, btn.dataset.externalUrl, btn.dataset.embedTitle);
      });
    });
    document.querySelectorAll("[data-embed-close]").forEach((el) => {
      el.addEventListener("click", closeEmbedModal);
    });
  }

  function openEmbedModal(embedUrl, externalUrl, title) {
    const modal = $("#embedModal");
    const frame = $("#embedFrame");
    $("#embedModalTitle").textContent = title || "";
    frame.src = embedUrl;
    const link = $("#embedExternalLink");
    link.href = externalUrl || embedUrl;
    link.textContent = t("videos.embedOpen");
    modal.hidden = false;
    document.body.classList.add("modal-open");
  }

  function closeEmbedModal() {
    const modal = $("#embedModal");
    modal.hidden = true;
    $("#embedFrame").src = "";
    document.body.classList.remove("modal-open");
  }

  function renderVideoLink(src) {
    const tierLabel = t(`videos.tier.${src.tier}`) || src.tier;
    const auth = src.requires_auth ? ` · ${t("videos.requiresAuth")}` : "";
    const langLabel = src.language ? src.language.toUpperCase() : "";
    return `
      <a class="video-link" href="${src.url}" target="_blank" rel="noopener noreferrer">
        <div class="video-link-info">
          <div class="video-link-name">${escapeHtml(src.name)} <span class="lang-flag">${langLabel}</span></div>
          <div class="video-link-meta">${tierLabel}${auth}</div>
        </div>
        <span class="video-open">${t("videos.open")} &rarr;</span>
      </a>
    `;
  }

  function setLang(newLang) {
    lang = newLang;
    localStorage.setItem(LANG_KEY, lang);
    loadI18n().then(() => {
      renderSelected();
      doSearch();
    });
  }

  document.querySelectorAll(".lang-btn").forEach((btn) => {
    btn.addEventListener("click", () => setLang(btn.dataset.lang));
  });

  $("#searchInput").addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(doSearch, 280);
  });

  $("#searchMode").addEventListener("change", doSearch);
  $("#kindFilter").addEventListener("change", doSearch);
  $("#findVideosBtn").addEventListener("click", () => findVideos(false));
  $("#refreshVideosBtn").addEventListener("click", () => findVideos(true));
  $("#clearSelectedBtn").addEventListener("click", () => {
    selected.clear();
    saveSelected();
    renderSelected();
    $("#videoLinks").innerHTML = "";
    $("#videosEmpty").style.display = "block";
    $("#refreshVideosBtn").hidden = true;
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !$("#embedModal").hidden) {
      closeEmbedModal();
    }
    if (e.key === "/" && document.activeElement !== $("#searchInput")) {
      e.preventDefault();
      $("#searchInput").focus();
    }
    if (document.activeElement !== $("#searchInput")) return;
    if (e.key === "ArrowDown" && lastResults.length) {
      e.preventDefault();
      resultIndex = Math.min(resultIndex + 1, lastResults.length - 1);
      highlightResult();
    }
    if (e.key === "ArrowUp" && lastResults.length) {
      e.preventDefault();
      resultIndex = Math.max(resultIndex - 1, 0);
      highlightResult();
    }
    if (e.key === "Enter" && resultIndex >= 0 && lastResults[resultIndex]) {
      e.preventDefault();
      addTerm(lastResults[resultIndex].id);
    }
  });

  loadSelected();
  loadI18n().then(() => {
    renderSelected();
    renderExamples();
  });
})();
