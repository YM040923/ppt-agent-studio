async function readJsonResponse(res, label) {
  const text = await res.text();
  let data = {};
  if (text) {
    try {
      data = JSON.parse(text);
    } catch (err) {
      throw new Error(`${label} 返回了非 JSON 内容`);
    }
  }
  if (!res.ok) throw new Error(data.error || `${label} 失败`);
  return data;
}

async function apiGet(url) {
  const res = await fetch(url);
  return readJsonResponse(res, `GET ${url}`);
}

async function apiPost(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return readJsonResponse(res, `POST ${url}`);
}

async function apiDelete(url) {
  const res = await fetch(url, { method: "DELETE" });
  return readJsonResponse(res, `DELETE ${url}`);
}

const state = {
  currentProject: null,
  templates: [],
  projects: [],
  busy: false,
  progressTimer: null,
  progressStartedAt: 0,
  projectPollTimer: null,
};

const tabMeta = {
  workspace: ["PPT 工作台", "先配置参数，再通过对话生成和调整 PPT。"],
  templates: ["模板库", "上传模板、AI 标准化、导出检查、删除管理。"],
  settings: ["AI 配置", "配置内容生成、润色和模板标准化所需的模型接口。"],
};

const el = {
  rail: document.getElementById("rail"),
  collapseRail: document.getElementById("collapse-rail"),
  collapseSetup: document.getElementById("collapse-setup"),
  tabs: [...document.querySelectorAll(".tab")],
  views: [...document.querySelectorAll(".view")],
  chips: [...document.querySelectorAll(".chip")],
  pageTitle: document.getElementById("page-title"),
  pageSubtitle: document.getElementById("page-subtitle"),
  planSource: document.getElementById("plan-source"),
  railStatus: document.getElementById("rail-status"),

  templateForm: document.getElementById("template-form"),
  templateFile: document.getElementById("template-file"),
  filePickerText: document.getElementById("file-picker-text"),
  templateUploadStatus: document.getElementById("template-upload-status"),
  templateList: document.getElementById("template-list"),
  templatePreview: document.getElementById("template-preview"),
  refreshTemplatesBtn: document.getElementById("refresh-templates"),

  projectForm: document.getElementById("project-form"),
  templateId: document.getElementById("template-id"),
  projectId: document.getElementById("project-id"),
  projectStatus: document.getElementById("project-status"),
  loadProjectBtn: document.getElementById("load-project-btn"),
  generateBtn: document.getElementById("generate-btn"),

  chatLog: document.getElementById("chat-log"),
  chatSubtitle: document.getElementById("chat-subtitle"),
  activityIndicator: document.getElementById("activity-indicator"),
  chatForm: document.getElementById("chat-form"),
  chatMessage: document.getElementById("chat-message"),
  sendBtn: document.getElementById("send-btn"),
  composerHint: document.getElementById("composer-hint"),
  downloadLink: document.getElementById("download-link"),
  downloadLinkTop: document.getElementById("download-link-top"),

  settingsForm: document.getElementById("settings-form"),
  settingsStatus: document.getElementById("settings-status"),
  settingsHint: document.getElementById("settings-hint"),
  openaiBaseUrl: document.getElementById("openai-base-url"),
  openaiModel: document.getElementById("openai-model"),
  openaiApiKey: document.getElementById("openai-api-key"),
  clearApiKey: document.getElementById("clear-api-key"),
  testAiBtn: document.getElementById("test-ai-btn"),
};

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function shortId(value) {
  const text = String(value || "");
  return text.length > 10 ? `${text.slice(0, 6)}...${text.slice(-4)}` : text;
}

function setStatus(node, message = "", level = "error") {
  node.classList.remove("ok", "info");
  if (level === "ok") node.classList.add("ok");
  if (level === "info") node.classList.add("info");
  node.textContent = message;
}

function setBusy(active, message = "") {
  state.busy = active;
  el.activityIndicator.classList.toggle("hidden", !active);
  if (message) el.activityIndicator.textContent = message;
  el.generateBtn.disabled = active;
  el.sendBtn.disabled = active;
  el.composerHint.textContent = active ? message : "消息会立即显示，后台完成后自动更新。";
}

function switchTab(name) {
  for (const tab of el.tabs) tab.classList.toggle("active", tab.dataset.tab === name);
  for (const view of el.views) view.classList.toggle("active", view.id === name);
  const meta = tabMeta[name] || tabMeta.workspace;
  el.pageTitle.textContent = meta[0];
  el.pageSubtitle.textContent = meta[1];
}

function addMessage(role, content, options = {}) {
  const row = document.createElement("div");
  row.className = `msg-row ${role}`;
  if (options.pending) row.classList.add("pending");
  if (options.id) row.dataset.messageId = options.id;

  const avatar = document.createElement("div");
  avatar.className = "msg-avatar";
  avatar.textContent = role === "user" ? "你" : "AI";

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";
  bubble.textContent = content;

  row.appendChild(avatar);
  row.appendChild(bubble);
  el.chatLog.appendChild(row);
  el.chatLog.scrollTop = el.chatLog.scrollHeight;
  return row;
}

function removePendingMessages() {
  el.chatLog.querySelectorAll(".msg-row.pending").forEach((node) => node.remove());
}

function renderConversation(conversation) {
  el.chatLog.innerHTML = "";
  const list = Array.isArray(conversation) ? conversation : [];
  if (!list.length) {
    addMessage("assistant", "先创建或加载项目。之后你发消息、点生成，我会在这里显示收到、规划、写入、检查和下载状态。");
    return;
  }
  for (const msg of list) addMessage(msg.role === "user" ? "user" : "assistant", msg.content || "");
}

function addConfirmOutlineAction(project) {
  if (!project?.project_id || !project.draft_plan || project.outline_confirmed || project.status === "generated") return;
  if (el.chatLog.querySelector("[data-outline-confirm]")) return;
  const row = addMessage("assistant", "大纲已在上面返回。确认后才会开始写入模板生成 PPT。", { id: "outline-confirm-action" });
  row.dataset.outlineConfirm = "true";
  const bubble = row.querySelector(".msg-bubble");
  const button = document.createElement("button");
  button.type = "button";
  button.className = "confirm-generate-btn";
  button.textContent = "确认并生成 PPT";
  button.addEventListener("click", () => confirmAndGenerate(project.project_id));
  bubble.appendChild(document.createElement("br"));
  bubble.appendChild(button);
}

function addAiFallbackChoice(projectId, message) {
  if (!projectId) return;
  if (el.chatLog.querySelector("[data-ai-fallback-choice]")) return;
  const row = addMessage("assistant", message || "AI 连接不可用。请选择下一步。", { id: "ai-fallback-choice" });
  row.dataset.aiFallbackChoice = "true";
  const bubble = row.querySelector(".msg-bubble");

  const actions = document.createElement("div");
  actions.className = "choice-actions";

  const settingsButton = document.createElement("button");
  settingsButton.type = "button";
  settingsButton.className = "ghost";
  settingsButton.textContent = "去 AI 配置";
  settingsButton.addEventListener("click", () => switchTab("settings"));

  const localButton = document.createElement("button");
  localButton.type = "button";
  localButton.className = "confirm-generate-btn";
  localButton.textContent = "继续不用 AI";
  localButton.addEventListener("click", () => planWithoutAi(projectId));

  actions.appendChild(settingsButton);
  actions.appendChild(localButton);
  bubble.appendChild(actions);
}

function updateDownload(project) {
  const ready = Boolean(project && project.output_pptx_path && project.project_id);
  const href = ready ? `/api/download?id=${encodeURIComponent(project.project_id)}` : "#";
  for (const node of [el.downloadLink, el.downloadLinkTop]) {
    node.href = href;
    node.classList.toggle("hidden", !ready && node === el.downloadLinkTop);
    node.classList.toggle("disabled", !ready);
  }
}

function rememberProject(project) {
  if (!project || !project.project_id) return;
  const exists = state.projects.some((item) => item.project_id === project.project_id);
  if (!exists) state.projects.unshift(project);
  renderProjectOptions();
}

function renderProjectOptions() {
  if (!state.projects.length) {
    el.projectId.innerHTML = `<option value="">暂无项目</option>`;
    return;
  }
  el.projectId.innerHTML = state.projects
    .map((project) => {
      const label = `${project.topic || "未命名"} (${shortId(project.project_id)})`;
      return `<option value="${escapeHtml(project.project_id)}">${escapeHtml(label)}</option>`;
    })
    .join("");
  if (state.currentProject?.project_id) el.projectId.value = state.currentProject.project_id;
}

function renderProject(project) {
  state.currentProject = project;
  rememberProject(project);
  renderConversation(project.conversation || []);
  addConfirmOutlineAction(project);

  const plan = project.draft_plan || project.plan || null;
  const source = plan?.source || "未生成";
  el.planSource.textContent = source === "未生成" ? "未生成" : `计划: ${source}`;
  el.railStatus.textContent = project.status || "已加载";
  el.chatSubtitle.textContent = project.topic
    ? `当前项目：${project.topic} (${shortId(project.project_id)})`
    : "当前项目已加载";
  updateDownload(project);
}

function renderTemplateOptions() {
  if (!state.templates.length) {
    el.templateId.innerHTML = `<option value="">请先上传模板</option>`;
    return;
  }
  el.templateId.innerHTML = state.templates
    .map((x) => {
      const label = `${x.template_name || "未命名模板"} (${shortId(x.template_id)})`;
      return `<option value="${escapeHtml(x.template_id)}">${escapeHtml(label)}</option>`;
    })
    .join("");
}

function renderTemplateList() {
  renderTemplateOptions();
  if (!state.templates.length) {
    el.templateList.innerHTML = `<div class="empty">暂无模板，请上传 .pptx。</div>`;
    return;
  }
  el.templateList.innerHTML = state.templates
    .map(
      (x) => `
        <article class="template-item">
          <div>
            <strong>${escapeHtml(x.template_name || "未命名模板")}</strong>
            <div class="template-meta">短 ID：${escapeHtml(shortId(x.template_id))}</div>
            <div class="template-meta">页数：${x.slide_count ?? "-"}　布局：${x.layout_count ?? "-"}</div>
          </div>
          <div class="template-actions">
            <button type="button" class="use-template" data-template-id="${escapeHtml(x.template_id)}">使用</button>
            <button type="button" class="standard-template ghost" data-template-id="${escapeHtml(x.template_id)}">标准化结果</button>
            <a class="ghost export-template" href="/api/template/export?id=${encodeURIComponent(x.template_id)}" target="_blank" rel="noreferrer">导出预览 PPT</a>
            <button type="button" class="copy-template ghost" data-template-id="${escapeHtml(x.template_id)}">复制 ID</button>
            <button type="button" class="delete-template danger" data-template-id="${escapeHtml(x.template_id)}">删除</button>
          </div>
        </article>
      `
    )
    .join("");
}

async function refreshTemplates() {
  el.templateList.innerHTML = `<div class="empty">正在加载模板...</div>`;
  const data = await apiGet("/api/templates");
  state.templates = data.items || [];
  renderTemplateList();
}

function renderAiStandardization(ai) {
  if (!ai || typeof ai !== "object") {
    return `<div class="empty">暂无 AI 标准化信息。</div>`;
  }
  const used = Boolean(ai.ai_used);
  const roles = Array.isArray(ai.layout_roles) ? ai.layout_roles : [];
  const routes = Array.isArray(ai.slide_routes) ? ai.slide_routes : [];
  const deckFlow = Array.isArray(ai.deck_flow) ? ai.deck_flow : [];
  const bindings = Array.isArray(ai.slot_bindings) ? ai.slot_bindings : [];
  const notes = Array.isArray(ai.normalization_notes) ? ai.normalization_notes : [];
  const rules = ai.content_rules && typeof ai.content_rules === "object" ? ai.content_rules : {};
  return `
    <div class="standard-card ${used ? "ok" : "warn"}">
      <strong>${used ? "AI 已参与标准化" : "已生成本地标准化合同"}</strong>
      <span>${escapeHtml(ai.summary || "-")}</span>
    </div>
    <h4>PPT 结构</h4>
    <div class="flow-row">
      ${deckFlow.map((item) => `<span>${escapeHtml(item)}</span>`).join("") || "<span>cover</span><span>toc</span><span>section</span><span>content</span><span>closing</span>"}
    </div>
    <div class="standard-card ok">
      <strong>排版规则</strong>
      <span>正文最小字号：${escapeHtml(rules.min_body_font_size_pt || 16)}pt；目录标题建议不超过 ${escapeHtml(rules.toc_title_max_chars || 14)} 字；正文页优先匹配知识点数量并避免重复版式。</span>
    </div>
    <h4>版式角色</h4>
    <div class="layout-list">
      ${roles.slice(0, 12).map((row) => `
        <div class="layout-row">
          <span>${escapeHtml(row.layout || "-")}</span>
          <em>${escapeHtml(row.role || "content")}</em>
          <b>${Math.round(Number(row.confidence || 0) * 100)}%</b>
        </div>
      `).join("") || "<div class='empty'>暂无 AI 版式角色。</div>"}
    </div>
    <h4>页面路由</h4>
    <div class="layout-list">
      ${routes.slice(0, 12).map((row) => `
        <div class="layout-row">
          <span>第 ${row.prototype_index ?? "-"} 页</span>
          <em>${escapeHtml(row.role || "content")}</em>
          <b>${escapeHtml(row.copy_pattern || "general")}</b>
        </div>
      `).join("") || "<div class='empty'>暂无 AI 页面路由。</div>"}
    </div>
    <h4>文本框绑定</h4>
    <div class="layout-list">
      ${bindings.slice(0, 16).map((row) => `
        <div class="layout-row">
          <span>第 ${row.prototype_index ?? "-"} 页 / ${escapeHtml(row.slot_id || "-")}</span>
          <em>${escapeHtml(row.semantic || "body")}</em>
          <b>${escapeHtml(row.min_font_size_pt || 16)}pt+</b>
        </div>
      `).join("") || "<div class='empty'>暂无文本框绑定。</div>"}
    </div>
    <h4>标准化说明</h4>
    <div class="note-list">
      ${notes.map((note) => `<div>${escapeHtml(note)}</div>`).join("") || "<div class='empty'>暂无说明。</div>"}
    </div>
  `;
}

async function loadTemplatePreview(templateId) {
  el.templatePreview.innerHTML = "正在读取标准化结果...";
  const data = await apiGet(`/api/template?id=${encodeURIComponent(templateId)}`);
  const spec = data.spec || {};
  const layouts = Array.isArray(spec.layouts) ? spec.layouts : [];
  const prototypes = Array.isArray(spec.prototypes) ? spec.prototypes : [];
  el.templatePreview.innerHTML = `
    <div class="preview-grid">
      <div><strong>模板名</strong><span>${escapeHtml(data.template_name || "-")}</span></div>
      <div><strong>短 ID</strong><code>${escapeHtml(shortId(data.template_id || "-"))}</code></div>
      <div><strong>页数</strong><span>${spec.slide_count ?? "-"}</span></div>
      <div><strong>布局数</strong><span>${spec.layout_count ?? "-"}</span></div>
      <div><strong>母版数</strong><span>${spec.master_count ?? "-"}</span></div>
      <div><strong>图片引用</strong><span>${spec.stats?.image_refs_total ?? "-"}</span></div>
    </div>
    ${renderAiStandardization(spec.ai_standardization)}
    <h4>本地解析样例</h4>
    <div class="layout-list">
      ${prototypes.slice(0, 8).map((slide) => `
        <div class="prototype-row">
          <strong>第 ${slide.index ?? "-"} 页</strong>
          <span>${escapeHtml(slide.text_preview || "无文字预览")}</span>
        </div>
      `).join("") || "<div class='empty'>没有页面原型信息。</div>"}
    </div>
    <h4>布局摘要</h4>
    <div class="layout-list">
      ${layouts.slice(0, 8).map((layout) => `
        <div class="layout-row">
          <span>${escapeHtml(layout.name || "未命名布局")}</span>
          <em>${escapeHtml(layout.layout_type || "-")}</em>
          <b>${layout.placeholder_count ?? 0} 占位符</b>
        </div>
      `).join("") || "<div class='empty'>没有布局信息。</div>"}
    </div>
  `;
}

async function loadSettings() {
  const data = await apiGet("/api/settings");
  el.openaiBaseUrl.value = data.openai_base_url || "";
  el.openaiModel.value = data.openai_model || "";
  el.settingsHint.textContent = data.has_api_key
    ? "已检测到 API Key。生成、润色和模板 AI 标准化都会使用该配置。"
    : "未配置 API Key 时，PPT 内容会使用本地 fallback，模板只会做本地解析。";
}

async function handleTemplateUpload(event) {
  event.preventDefault();
  if (!el.templateFile.files.length) {
    setStatus(el.templateUploadStatus, "请先选择 .pptx 模板。");
    return;
  }
  setStatus(el.templateUploadStatus, "正在上传、解析模板，并调用模板标准化 agent...", "info");
  const form = new FormData();
  form.append("file", el.templateFile.files[0]);
  try {
    const res = await fetch("/api/templates", { method: "POST", body: form });
    const data = await readJsonResponse(res, "上传模板");
    const ai = data.spec?.ai_standardization;
    setStatus(
      el.templateUploadStatus,
      ai?.ai_used ? `上传成功，AI 已标准化：${shortId(data.template_id)}` : `上传成功，已本地解析：${shortId(data.template_id)}。配置 API Key 后可重新上传做 AI 标准化。`,
      "ok",
    );
    el.templateFile.value = "";
    el.filePickerText.textContent = "选择 PPTX 模板";
    await refreshTemplates();
    await loadTemplatePreview(data.template_id);
    switchTab("templates");
  } catch (err) {
    setStatus(el.templateUploadStatus, err.message, "error");
  }
}

async function handleProjectCreate(event) {
  event.preventDefault();
  setStatus(el.projectStatus, "正在创建项目...", "info");
  try {
    const project = await apiPost("/api/projects", {
      topic: document.getElementById("topic").value.trim(),
      template_id: el.templateId.value,
      slide_count: Number(document.getElementById("slide-count").value || 12),
      audience: document.getElementById("audience").value.trim(),
      tone: document.getElementById("tone").value.trim(),
    });
    renderProject(project);
    addMessage("assistant", `项目已创建：${project.topic}\n短 ID：${shortId(project.project_id)}\n你可以直接点“生成 PPT”，或先告诉我怎么改。`);
    setStatus(el.projectStatus, "项目已创建。", "ok");
  } catch (err) {
    setStatus(el.projectStatus, err.message, "error");
  }
}

async function handleLoadProject() {
  const id = el.projectId.value;
  if (!id) {
    setStatus(el.projectStatus, "请先选择项目。");
    return;
  }
  const project = await apiGet(`/api/project?id=${encodeURIComponent(id)}`);
  renderProject(project);
  setStatus(el.projectStatus, "项目已加载。", "ok");
}

function startProgress(label, steps) {
  stopProgress();
  const progressRow = addMessage("assistant", "", { pending: true, id: "generation-progress" });
  state.progressStartedAt = Date.now();
  updateProgress(label, Array.isArray(steps) ? steps : []);
  state.progressTimer = setInterval(() => updateProgress(label, Array.isArray(steps) ? steps : []), 1000);
  return progressRow;
}

function updateProgress(label, steps = []) {
  const bubble = el.chatLog.querySelector('[data-message-id="generation-progress"] .msg-bubble');
  if (!bubble) return;
  const elapsed = state.progressStartedAt ? Math.max(0, Math.floor((Date.now() - state.progressStartedAt) / 1000)) : 0;
  const current = steps.length ? `\n\n当前：${steps[0]}` : "";
  bubble.textContent = `${label}${current}\n\n已耗时 ${elapsed} 秒，服务器还在处理时这里会继续计时。`;
}

function replaceProgress(content) {
  if (state.progressTimer) clearInterval(state.progressTimer);
  state.progressTimer = null;
  state.progressStartedAt = 0;
  const bubble = el.chatLog.querySelector('[data-message-id="generation-progress"] .msg-bubble');
  if (bubble) bubble.textContent = content;
}

function stopProgress(remove = true) {
  if (state.progressTimer) clearInterval(state.progressTimer);
  state.progressTimer = null;
  state.progressStartedAt = 0;
  if (remove) removePendingMessages();
}

async function startProjectPolling(id) {
  stopProjectPolling();
  state.projectPollTimer = setInterval(async () => {
    try {
      const project = await apiGet(`/api/project?id=${encodeURIComponent(id)}`);
      state.currentProject = project;
      renderConversation(project.conversation || []);
      addConfirmOutlineAction(project);
      updateDownload(project);
      el.railStatus.textContent = project.status || "generating";
      el.projectStatus.textContent = project.status === "generated" ? "PPT 已生成，可以下载。" : "正在生成 PPT，进度已同步到对话框。";
      if (project.status === "generated") stopProjectPolling();
    } catch (err) {
      console.warn("project polling failed", err);
    }
  }, 1200);
}

function stopProjectPolling() {
  if (state.projectPollTimer) clearInterval(state.projectPollTimer);
  state.projectPollTimer = null;
}

async function handleChatSubmit(event) {
  event.preventDefault();
  const id = state.currentProject?.project_id || el.projectId.value;
  const message = el.chatMessage.value.trim();
  if (!id) {
    setStatus(el.projectStatus, "请先创建或加载项目。");
    return;
  }
  if (!message) return;

  el.chatMessage.value = "";
  addMessage("user", message);
  startProgress("已收到你的修改要求，正在处理：", [
    "1. 读取当前项目和对话上下文",
    "2. 调用 AI 更新内容计划",
    "3. 按模板版式检查每页文案",
    "4. 保存内容计划并刷新对话",
  ]);
  setBusy(true, "AI 正在更新内容计划...");
  setStatus(el.projectStatus, "请求已发送，正在等待 AI 返回...", "info");
  try {
    const out = await apiPost("/api/plan", { project_id: id, message });
    stopProgress();
    if (out.requires_user_choice) {
      renderProject(out.project);
      addAiFallbackChoice(id, out.assistant_message);
      setStatus(el.projectStatus, "AI 连接不可用，请选择是否继续不用 AI。", "info");
      return;
    }
    renderProject(out.project);
    setStatus(el.projectStatus, "内容计划已更新。", "ok");
  } catch (err) {
    stopProgress();
    addMessage("assistant", `处理失败：${err.message}`);
    setStatus(el.projectStatus, err.message, "error");
  } finally {
    setBusy(false);
  }
}

async function handleGenerate() {
  const id = state.currentProject?.project_id || el.projectId.value;
  if (!id) {
    setStatus(el.projectStatus, "请先创建或加载项目。");
    return;
  }
  const current = state.currentProject;
  if (!current?.draft_plan || !current?.outline_confirmed) {
    startProgress("已收到生成请求。正在等待服务端返回真实处理阶段；确认前不会写入模板。", []);
    setBusy(true, "正在生成完整大纲...");
    setStatus(el.projectStatus, "正在生成完整大纲，完成后会显示在对话框里。", "info");
    try {
      await startProjectPolling(id);
      const out = await apiPost("/api/plan", { project_id: id, message: "" });
      stopProjectPolling();
      stopProgress();
      if (out.requires_user_choice) {
        renderProject(out.project);
        addAiFallbackChoice(id, out.assistant_message);
        setStatus(el.projectStatus, "AI 连接不可用，请选择是否继续不用 AI。", "info");
        return;
      }
      renderProject(out.project);
      setStatus(el.projectStatus, "大纲已生成，请在对话框确认后继续。", "ok");
    } catch (err) {
      stopProjectPolling();
      stopProgress();
      addMessage("assistant", `生成大纲失败：${err.message}`);
      setStatus(el.projectStatus, err.message, "error");
    } finally {
      stopProjectPolling();
      setBusy(false);
    }
    return;
  }
  await confirmAndGenerate(id);
}

async function planWithoutAi(id) {
  if (!id) return;
  startProgress("已选择不用 AI，正在按本地规则生成可检查的大纲。", [
    "本地规则会明确标记来源，不会伪装成 AI 生成。",
  ]);
  setBusy(true, "正在使用本地规则生成大纲...");
  setStatus(el.projectStatus, "已获得授权：不用 AI，改用本地规则生成大纲。", "info");
  try {
    await startProjectPolling(id);
    const out = await apiPost("/api/plan", { project_id: id, message: "", allow_without_ai: true });
    stopProjectPolling();
    stopProgress();
    renderProject(out.project);
    setStatus(el.projectStatus, "本地规则大纲已生成，请检查并确认。", "ok");
  } catch (err) {
    stopProjectPolling();
    stopProgress();
    addMessage("assistant", `本地规则生成失败：${err.message}`);
    setStatus(el.projectStatus, err.message, "error");
  } finally {
    stopProjectPolling();
    setBusy(false);
  }
}

async function confirmAndGenerate(id) {
  if (!id) return;
  startProgress("已收到确认。正在等待服务端真实生成阶段；完成后会显示下载按钮。", []);
  setBusy(true, "正在生成 PPT...");
  setStatus(el.projectStatus, "正在写入模板并运行检查，请不要重复点击。", "info");
  try {
    const confirmed = await apiPost("/api/confirm-plan", { project_id: id });
    state.currentProject = confirmed;
    replaceProgress("大纲已确认。\n\n正在等待服务端阶段消息；对话框会同步显示真实进度。");
    await startProjectPolling(id);
    const project = await apiPost("/api/generate", { project_id: id });
    stopProjectPolling();
    stopProgress();
    renderProject(project);
    addMessage("assistant", "PPT 已生成。顶部和参数区的“下载 PPT”按钮已可用。");
    setStatus(el.projectStatus, "PPT 已生成，可以下载。", "ok");
  } catch (err) {
    stopProjectPolling();
    stopProgress();
    addMessage("assistant", `生成失败：${err.message}`);
    setStatus(el.projectStatus, err.message, "error");
  } finally {
    stopProjectPolling();
    setBusy(false);
  }
}

async function handleSettingsSave(event) {
  event.preventDefault();
  setStatus(el.settingsStatus, "正在保存配置...", "info");
  try {
    const out = await apiPost("/api/settings", {
      openai_base_url: el.openaiBaseUrl.value.trim(),
      openai_model: el.openaiModel.value.trim(),
      openai_api_key: el.openaiApiKey.value.trim(),
      clear_api_key: el.clearApiKey.checked,
    });
    el.openaiApiKey.value = "";
    el.clearApiKey.checked = false;
    el.settingsHint.textContent = out.has_api_key
      ? "配置已保存。生成、润色和模板 AI 标准化都会使用该配置。"
      : "配置已保存，目前没有 API Key，将使用本地 fallback。";
    setStatus(el.settingsStatus, "配置保存成功。", "ok");
  } catch (err) {
    setStatus(el.settingsStatus, err.message, "error");
  }
}

async function handleAiConnectionTest() {
  setStatus(el.settingsStatus, "正在测试 AI 连接...", "info");
  try {
    const out = await apiGet("/api/ai/check");
    if (out.ok) {
      setStatus(el.settingsStatus, out.message || "AI 连接测试通过。", "ok");
    } else {
      setStatus(el.settingsStatus, out.message || "AI 连接测试失败。", "error");
    }
  } catch (err) {
    setStatus(el.settingsStatus, err.message, "error");
  }
}

function bindEvents() {
  for (const tab of el.tabs) tab.addEventListener("click", () => switchTab(tab.dataset.tab));
  el.collapseRail.addEventListener("click", () => {
    const collapsed = document.body.classList.toggle("rail-collapsed");
    el.collapseRail.textContent = collapsed ? "›" : "‹";
    el.collapseRail.title = collapsed ? "展开侧边栏" : "折叠侧边栏";
  });
  el.collapseSetup.addEventListener("click", () => {
    const collapsed = document.body.classList.toggle("setup-collapsed");
    el.collapseSetup.textContent = collapsed ? "展开" : "折叠";
  });

  for (const chip of el.chips) {
    chip.addEventListener("click", () => {
      el.chatMessage.value = chip.dataset.prompt || "";
      el.chatMessage.focus();
    });
  }

  el.templateFile.addEventListener("change", () => {
    el.filePickerText.textContent = el.templateFile.files[0]?.name || "选择 PPTX 模板";
  });

  el.templateList.addEventListener("click", async (event) => {
    const target = event.target;
    const useButton = target.closest(".use-template");
    const standardButton = target.closest(".standard-template");
    const copyButton = target.closest(".copy-template");
    const deleteButton = target.closest(".delete-template");
    if (useButton) {
      el.templateId.value = useButton.dataset.templateId || "";
      switchTab("workspace");
      setStatus(el.projectStatus, `已选择模板：${shortId(el.templateId.value)}`, "info");
    }
    if (standardButton) await loadTemplatePreview(standardButton.dataset.templateId || "");
    if (copyButton) {
      await navigator.clipboard.writeText(copyButton.dataset.templateId || "");
      copyButton.textContent = "已复制";
      setTimeout(() => (copyButton.textContent = "复制 ID"), 1000);
    }
    if (deleteButton) {
      const id = deleteButton.dataset.templateId || "";
      if (!window.confirm(`删除模板 ${shortId(id)}？`)) return;
      await apiDelete(`/api/template?id=${encodeURIComponent(id)}`);
      if (el.templateId.value === id) el.templateId.value = "";
      el.templatePreview.innerHTML = "模板已删除。";
      await refreshTemplates();
    }
  });

  el.chatMessage.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      el.chatForm.requestSubmit();
    }
  });

  el.templateForm.addEventListener("submit", handleTemplateUpload);
  el.refreshTemplatesBtn.addEventListener("click", refreshTemplates);
  el.projectForm.addEventListener("submit", handleProjectCreate);
  el.loadProjectBtn.addEventListener("click", handleLoadProject);
  el.chatForm.addEventListener("submit", handleChatSubmit);
  el.generateBtn.addEventListener("click", handleGenerate);
  el.settingsForm.addEventListener("submit", handleSettingsSave);
  el.testAiBtn.addEventListener("click", handleAiConnectionTest);
}

async function init() {
  bindEvents();
  switchTab("workspace");
  renderProjectOptions();
  renderConversation([]);
  updateDownload(null);
  try {
    await refreshTemplates();
    await loadSettings();
  } catch (err) {
    setStatus(el.projectStatus, err.message, "error");
  }
}

init();
