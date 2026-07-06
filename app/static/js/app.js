(() => {
  const LANG_KEY = "svf_lang";
  let lang = localStorage.getItem(LANG_KEY) || window.APP_LANG || "en";
  let i18n = {};
  let selected = new Map();
  let searchTimer = null;

  const $ = (sel) => document.querySelector(sel);

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
    const kindAll = document.querySelector('#kindFilter option[value=""]');
    if (kindAll) kindAll.textContent = lang === "ro" ? "Toate" : "All";
  }

  function t(key) {
    return i18n[key] || key;
  }

  function renderSelected() {
    const chips = $("#selectedChips");
    const empty = $("#selectedEmpty");
    const btn = $("#findVideosBtn");
    chips.innerHTML = "";

    if (selected.size === 0) {
      empty.style.display = "block";
      btn.disabled = true;
      return;
    }
    empty.style.display = "none";
    btn.disabled = false;

    selected.forEach((term) => {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.innerHTML = `
        <span>${escapeHtml(term.display_name)}${term.fallback_en ? ` <small>[${t("results.fallbackEn")}]</small>` : ""}</span>
        <button type="button" aria-label="${t("selected.remove")}" data-id="${term.id}">&times;</button>
      `;
      chip.querySelector("button").addEventListener("click", () => {
        selected.delete(term.id);
        renderSelected();
      });
      chips.appendChild(chip);
    });
  }

  function escapeHtml(str) {
    return str.replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  async function doSearch() {
    const q = $("#searchInput").value.trim();
    const container = $("#searchResults");
    if (!q) {
      container.innerHTML = "";
      return;
    }

    container.innerHTML = `<p class="empty-msg">${t("search.loading")}</p>`;
    const mode = $("#searchMode").value;
    const kind = $("#kindFilter").value;
    const params = new URLSearchParams({ q, lang, mode, limit: "20" });
    if (kind) params.set("kind", kind);

    try {
      const res = await fetch(`/api/terms/search?${params}`);
      const data = await res.json();
      if (!data.results.length) {
        container.innerHTML = `<p class="empty-msg">${t("search.noResults")}</p>`;
        return;
      }
      container.innerHTML = data.results.map(renderResult).join("");
      container.querySelectorAll(".add-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
          const id = Number(btn.dataset.id);
          const term = data.results.find((r) => r.id === id);
          if (term) {
            selected.set(id, term);
            renderSelected();
          }
        });
      });
    } catch {
      container.innerHTML = `<p class="empty-msg">${t("error.generic")}</p>`;
    }
  }

  function renderResult(term) {
    const kindLabel = term.kind === "procedure" ? t("results.kind.procedure") : t("results.kind.diagnosis");
    const layerLabel = term.layer === "curated" ? t("results.layer.curated") : t("results.layer.comprehensive");
    const code = term.code ? `<span class="tag">${t("results.code")}: ${escapeHtml(term.code)}</span>` : "";
    const enBadge = term.fallback_en ? `<span class="tag en-fallback">${t("results.fallbackEn")}</span>` : "";
    const score = term.score != null ? `<span class="tag">${(term.score * 100).toFixed(0)}%</span>` : "";

    return `
      <div class="result-item">
        <div class="result-meta">
          <div class="result-name">${escapeHtml(term.display_name)}</div>
          <div class="result-tags">
            <span class="tag">${kindLabel}</span>
            <span class="tag">${layerLabel}</span>
            ${code}${enBadge}${score}
          </div>
        </div>
        <button type="button" class="add-btn" data-id="${term.id}" ${selected.has(term.id) ? "disabled" : ""}>
          ${t("results.add")}
        </button>
      </div>
    `;
  }

  async function findVideos() {
    const container = $("#videoLinks");
    const empty = $("#videosEmpty");
    if (selected.size === 0) return;

    empty.style.display = "none";
    container.innerHTML = `<p class="empty-msg">${t("videos.loading")}</p>`;

    const ids = Array.from(selected.keys()).join(",");
    try {
      const res = await fetch(`/api/videos/links?term_ids=${ids}&lang=${lang}`);
      const data = await res.json();
      if (!data.sources.length) {
        container.innerHTML = `<p class="empty-msg">${t("videos.empty")}</p>`;
        return;
      }
      container.innerHTML = data.sources.map((src) => {
        const tierLabel = t(`videos.tier.${src.tier}`) || src.tier;
        const auth = src.requires_auth ? ` · ${t("videos.requiresAuth")}` : "";
        return `
          <a class="video-link" href="${src.url}" target="_blank" rel="noopener noreferrer">
            <div class="video-link-info">
              <div class="video-link-name">${escapeHtml(src.name)}</div>
              <div class="video-link-meta">${tierLabel}${auth}</div>
            </div>
            <span class="video-open">${t("videos.open")} &rarr;</span>
          </a>
        `;
      }).join("");
    } catch {
      container.innerHTML = `<p class="empty-msg">${t("error.generic")}</p>`;
    }
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
  $("#findVideosBtn").addEventListener("click", findVideos);

  loadI18n();
  renderSelected();
})();
