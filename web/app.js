/* ===== RAG 知识库助手 · 前端逻辑 ===== */
const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);
let busy = false;

// ---------- 基础 ----------
async function api(path, body) {
  const opt = body === undefined
    ? {}
    : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const r = await fetch(path, opt);
  return r.json();
}
function toast(msg, isErr) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast" + (isErr ? " err" : "");
  clearTimeout(t._tm);
  t._tm = setTimeout(() => t.classList.add("hidden"), 3200);
}
function setStatus(text, cls) {
  const p = $("#status-pill");
  p.textContent = text;
  p.className = "pill" + (cls ? " " + cls : "");
}
function esc(s) {
  return String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// ---------- 状态刷新 ----------
async function refresh() {
  const s = await api("/api/state");
  $("#session-id").textContent = s.session_id;
  $("#history-len").textContent = s.history_len + " 条";
  $("#mode-label").textContent = s.mode;
  $("#model-name").textContent = s.model;
  $("#k-value").textContent = s.k;
  $("#kb-k").textContent = s.k;
  if ($("#k-slider").value != s.k) $("#k-slider").value = s.k;
  $$(".mode-btn").forEach(b => b.classList.toggle("active", b.dataset.mode === s.mode));
  const banner = $("#mode-banner");
  if (s.mode === "direct") banner.classList.remove("hidden");
  else banner.classList.add("hidden");
  if (s.index.exists) {
    $("#kb-empty").classList.add("hidden");
    $("#kb-stats").classList.remove("hidden");
    $("#kb-docs").textContent = s.index.docs;
    $("#kb-chunks").textContent = s.index.chunks;
    $("#kb-sources").innerHTML = s.index.sources.map(x => `<li title="${esc(x)}">${esc(x)}</li>`).join("");
  } else {
    $("#kb-empty").classList.remove("hidden");
    $("#kb-stats").classList.add("hidden");
    $("#kb-sources").innerHTML = "";
  }
}

// ---------- Tab 切换 ----------
$$(".tab").forEach(t => t.onclick = () => {
  $$(".tab").forEach(x => x.classList.remove("active"));
  t.classList.add("active");
  $$(".panel").forEach(p => p.classList.remove("active"));
  $("#tab-" + t.dataset.tab).classList.add("active");
  if (t.dataset.tab === "compare") loadQuestions();
  if (t.dataset.tab === "files") loadFiles();
  if (t.dataset.tab === "guide") loadLogList();
});

// ---------- 知识库 ----------
$("#btn-index").onclick = async () => {
  if (busy) return;
  busy = true;
  setStatus("建库中…", "busy");
  $("#btn-index").disabled = true;
  try {
    const r = await api("/api/index", {});
    if (r.error) { toast(r.error, true); setStatus("建库失败", "err"); }
    else { toast(`建库成功：文档 ${r.docs} 份，片段 ${r.chunks} 条`); setStatus("就绪"); }
    await refresh();
  } catch (e) { toast("请求失败：" + e.message, true); setStatus("错误", "err"); }
  $("#btn-index").disabled = false;
  busy = false;
};

$("#btn-add-file").onclick = () => {
  $(".tab[data-tab=files]").click();
};

// ---------- 会话 ----------
$("#btn-new").onclick = async () => {
  await api("/api/new", {});
  $("#chat-list").innerHTML = "";
  toast("已开启新会话，旧上下文已清空（日志保留）");
  await refresh();
};
$$(".mode-btn").forEach(b => b.onclick = async () => {
  await api("/api/mode", { mode: b.dataset.mode });
  toast("已切换到 " + b.dataset.mode + " 模式，并开启新会话");
  await refresh();
});
$("#k-slider").onchange = async (e) => {
  await api("/api/k", { k: parseInt(e.target.value) });
  toast("Top-K 已调整，并开启新会话");
  await refresh();
};

// ---------- 对话 ----------
function addMsg(role, text) {
  const div = document.createElement("div");
  div.className = "msg msg-" + role;
  div.innerHTML = `<div class="msg-bubble"><span class="msg-text"></span></div>`;
  div.querySelector(".msg-text").textContent = text;
  $("#chat-list").appendChild(div);
  $("#chat-list").scrollTop = $("#chat-list").scrollHeight;
  return div;
}
function renderAnswer(row) {
  const isErr = row.status === "error";
  const div = addMsg(isErr ? "error" : "assistant", isErr ? ("错误：" + row.error) : row.answer);
  const bubble = div.querySelector(".msg-bubble");
  if (row.retrieved && row.retrieved.length) {
    const chips = document.createElement("div");
    chips.className = "msg-sources";
    chips.innerHTML = "来源：" + row.retrieved.map(h =>
      `<span class="src-chip" title="${esc(h.source)}">${esc(h.chunk_id)}</span>`).join("");
    bubble.appendChild(chips);
  }
  const meta = document.createElement("div");
  meta.className = "msg-meta";
  meta.innerHTML = `<span>${row.mode} · top_k=${row.top_k} · ${row.elapsed_ms}ms</span><a>查看本轮 messages</a>`;
  bubble.appendChild(meta);
  meta.querySelector("a").onclick = (e) => {
    let d = bubble.querySelector(".msg-detail");
    if (d) { d.remove(); return; }
    d = document.createElement("div");
    d.className = "msg-detail";
    d.textContent = JSON.stringify(row.messages || [], null, 2);
    bubble.appendChild(d);
  };
  $("#chat-list").scrollTop = $("#chat-list").scrollHeight;
}
async function send() {
  const q = $("#chat-input").value.trim();
  if (!q || busy) return;
  busy = true;
  $("#chat-input").value = "";
  const w = $(".welcome"); if (w) w.remove();
  addMsg("user", q);
  const t = addMsg("assistant", "");
  t.querySelector(".msg-bubble").innerHTML = '<span class="typing"><i></i><i></i><i></i></span>';
  setStatus("思考中…", "busy");
  try {
    const row = await api("/api/chat", { question: q });
    t.remove();
    renderAnswer(row);
    setStatus(row.status === "error" ? "出错" : "就绪", row.status === "error" ? "err" : "");
  } catch (e) {
    t.remove();
    addMsg("error", "请求失败：" + e.message);
    setStatus("错误", "err");
  }
  await refresh();
  busy = false;
}
$("#btn-send").onclick = send;
$("#chat-input").addEventListener("keydown", e => { if (e.key === "Enter") send(); });
document.addEventListener("click", e => {
  if (e.target.classList.contains("chip-q")) {
    $("#chat-input").value = e.target.textContent;
    send();
  }
});

// ---------- 检索 ----------
$("#btn-search").onclick = async () => {
  const q = $("#search-input").value.trim();
  if (!q || busy) return;
  busy = true;
  setStatus("检索中…", "busy");
  $("#search-results").innerHTML = "";
  try {
    const row = await api("/api/search", { question: q });
    if (row.status === "error") {
      $("#search-results").innerHTML = `<div class="hit-card" style="color:#be123c">错误：${esc(row.error)}</div>`;
    } else {
      $("#search-results").innerHTML = row.retrieved.map((h, i) => `
        <div class="hit-card">
          <div class="hit-head">
            <span class="hit-rank">${i + 1}</span>
            <span class="hit-id">${esc(h.chunk_id)}</span>
            <span class="hit-source">${esc(h.source)} · 字符 ${h.start}–${h.end}</span>
            <span class="hit-score">${h.score.toFixed(4)}</span>
          </div>
          <div class="score-track"><div class="score-bar" data-w="${Math.max(2, h.score * 100)}"></div></div>
          <div class="hit-text">${esc(h.text)}</div>
        </div>`).join("");
      requestAnimationFrame(() => $$(".score-bar").forEach(b => b.style.width = b.dataset.w + "%"));
    }
    setStatus(row.status === "error" ? "出错" : "就绪", row.status === "error" ? "err" : "");
  } catch (e) { toast("请求失败：" + e.message, true); setStatus("错误", "err"); }
  busy = false;
};
$("#search-input").addEventListener("keydown", e => { if (e.key === "Enter") $("#btn-search").click(); });

// ---------- 对照 ----------
async function loadQuestions() {
  const sel = $("#compare-select");
  if (sel.dataset.loaded) return;
  const r = await api("/api/questions");
  const qs = r.questions || [];
  qs.forEach((q, i) => {
    const text = q.question || q.Question || Object.values(q)[1] || Object.values(q)[0];
    const id = q.id || q.ID || Object.values(q)[0];
    const o = document.createElement("option");
    o.value = text;
    o.textContent = (id ? id + " " : "") + text;
    sel.appendChild(o);
  });
  sel.dataset.loaded = "1";
}
$("#compare-select").onchange = (e) => { $("#compare-input").value = e.target.value; };
$("#btn-compare").onclick = async () => {
  const q = $("#compare-input").value.trim();
  if (!q || busy) return;
  busy = true;
  setStatus("对照运行中…", "busy");
  $("#compare-results").innerHTML = "";
  try {
    const r = await api("/api/compare", { question: q });
    for (const mode of ["direct", "rag"]) {
      const row = r[mode];
      const div = document.createElement("div");
      div.className = "compare-col";
      const src = (row.retrieved || []).map(h => `<span class="src-chip">${esc(h.chunk_id)}</span>`).join(" ");
      div.innerHTML = `
        <h4><span class="badge badge-${mode}">${mode === "rag" ? "RAG 检索增强" : "Direct 直接问"}</span>
            <span style="font-size:11px;color:var(--muted)">${row.elapsed_ms}ms</span></h4>
        <div class="answer">${esc(row.status === "error" ? "错误：" + row.error : row.answer)}</div>
        ${src ? `<div class="msg-sources">来源：${src}</div>` : ""}
        ${row.usage ? `<div class="usage">tokens: ${esc(JSON.stringify(row.usage))}</div>` : ""}`;
      $("#compare-results").appendChild(div);
    }
    setStatus("就绪");
  } catch (e) { toast("请求失败：" + e.message, true); setStatus("错误", "err"); }
  busy = false;
};

// ---------- 日志 ----------
async function loadLogList() {
  const r = await api("/api/logs");
  const sel = $("#log-select");
  sel.innerHTML = '<option value="">—— 选择日志文件 ——</option>';
  (r.files || []).forEach(f => {
    const o = document.createElement("option");
    o.value = f; o.textContent = f;
    sel.appendChild(o);
  });
}
$("#btn-log").onclick = async () => {
  const name = $("#log-select").value;
  if (!name) return;
  const r = await api("/api/logs/" + encodeURIComponent(name));
  const v = $("#log-view");
  v.classList.remove("hidden");
  v.textContent = (r.rows || []).map(x => JSON.stringify(x, null, 2)).join("\n\n");
};

// ---------- 密钥 ----------
$("#btn-key").onclick = () => $("#key-modal").classList.remove("hidden");
$("#key-cancel").onclick = () => $("#key-modal").classList.add("hidden");
$("#key-save").onclick = async () => {
  const ck = $("#key-chat").value.trim();
  if (!ck) { toast("对话密钥不能为空", true); return; }
  const r = await api("/api/key", { chat_key: ck, embedding_key: $("#key-embed").value.trim() });
  if (r.error) { toast(r.error, true); return; }
  $("#key-modal").classList.add("hidden");
  toast("密钥已保存（仅存在服务端内存，重启需重输）");
  await refresh();
};

// ---------- 资料管理 ----------
let pendingFile = null;

async function loadFiles() {
  const r = await api("/api/files");
  const list = r.files || [];
  const box = $("#file-list");
  if (!list.length) {
    box.innerHTML = '<div class="empty-hint">data 文件夹里还没有资料</div>';
    return;
  }
  box.innerHTML = list.map(f => `
    <div class="file-item">
      <div class="fi-main">
        <div class="fi-name">${esc(f.name)}</div>
        <div class="fi-meta">${f.chars} 字 · ${esc(f.preview)}…</div>
      </div>
      <button class="fi-del" data-name="${esc(f.name)}">删除</button>
    </div>`).join("");
  box.querySelectorAll(".fi-del").forEach(b => {
    b.onclick = async () => {
      if (!confirm("确定删除 " + b.dataset.name + " 吗？删除后需要重建知识库。")) return;
      const res = await api("/api/files/delete", { name: b.dataset.name });
      if (res.error) { toast(res.error, true); return; }
      toast("已删除 " + res.name + "，请重建知识库");
      loadFiles();
    };
  });
}

async function reindex(silent) {
  const btn = $("#btn-reindex");
  btn.disabled = true;
  btn.textContent = "重建中…";
  const r = await api("/api/index", {});
  btn.disabled = false;
  btn.textContent = "🔄 保存后重建知识库（/index）";
  if (r.error) { toast(r.error, true); setStatus("建库失败", "err"); return null; }
  if (!silent) toast(`建库成功：文档 ${r.docs} 份，片段 ${r.chunks} 条`);
  await refresh();
  return r;
}

// 上传文件
$("#file-input").onchange = (e) => {
  pendingFile = e.target.files[0] || null;
  const hint = $("#upload-hint"), drop = $("#upload-drop");
  if (pendingFile) {
    hint.textContent = `已选择：${pendingFile.name}（${(pendingFile.size / 1024).toFixed(1)} KB）`;
    drop.classList.add("filled");
  } else {
    hint.textContent = "点击选择文件，或把文件拖到这里";
    drop.classList.remove("filled");
  }
};
["dragenter", "dragover"].forEach(ev => {
  $("#upload-drop").addEventListener(ev, e => { e.preventDefault(); $("#upload-drop").classList.add("drag"); });
});
["dragleave", "drop"].forEach(ev => {
  $("#upload-drop").addEventListener(ev, e => { e.preventDefault(); $("#upload-drop").classList.remove("drag"); });
});
$("#upload-drop").addEventListener("drop", e => {
  const f = e.dataTransfer.files[0];
  if (f) { pendingFile = f; $("#file-input").files = e.dataTransfer.files;
    $("#upload-hint").textContent = `已选择：${f.name}`; $("#upload-drop").classList.add("filled"); }
});

$("#btn-upload").onclick = async () => {
  if (!pendingFile) { toast("请先选择文件", true); return; }
  const btn = $("#btn-upload");
  btn.disabled = true;
  try {
    const isDocx = pendingFile.name.toLowerCase().endsWith(".docx");
    let payload = { name: pendingFile.name };
    if (isDocx) {
      const buf = await pendingFile.arrayBuffer();
      let bin = ""; const bytes = new Uint8Array(buf);
      for (let i = 0; i < bytes.length; i += 0x8000) {
        bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
      }
      payload.content_b64 = btoa(bin);
    } else {
      payload.content = await pendingFile.text();
    }
    const res = await api("/api/files/add", payload);
    if (res.error) { toast(res.error, true); return; }
    toast(`已保存 ${res.name}，正在重建知识库…`);
    pendingFile = null;
    $("#file-input").value = "";
    $("#upload-hint").textContent = "点击选择文件，或把文件拖到这里";
    $("#upload-drop").classList.remove("filled");
    await loadFiles();
    await reindex(true);
    toast(`完成：${res.name} 已加入知识库`);
  } finally { btn.disabled = false; }
};

// 新建资料
$("#btn-create").onclick = async () => {
  const title = $("#new-title").value.trim();
  const content = $("#new-content").value;
  if (!title) { toast("请填写标题", true); return; }
  if (!content.trim()) { toast("请填写正文内容", true); return; }
  const btn = $("#btn-create");
  btn.disabled = true;
  const res = await api("/api/files/add", { name: title + ".md", content });
  btn.disabled = false;
  if (res.error) { toast(res.error, true); return; }
  $("#new-title").value = ""; $("#new-content").value = "";
  toast(`已保存 ${res.name}，正在重建知识库…`);
  await loadFiles();
  await reindex(true);
  toast(`完成：${res.name} 已加入知识库`);
};

$("#btn-reindex").onclick = () => reindex(false);

// ---------- 主题切换 ----------
const THEME_KEY = "rag-theme-v2";   // 换键：忽略旧版本遗留的主题偏好
function applyTheme(theme, save) {
  document.body.dataset.theme = theme;
  $("#btn-theme").textContent = theme === "dark" ? "☀️" : "🌙";
  $("#btn-theme").title = theme === "dark" ? "切换到浅色" : "切换到深色";
  if (save) { try { localStorage.setItem(THEME_KEY, theme); } catch (e) { } }
}
$("#btn-theme").onclick = () => {
  applyTheme(document.body.dataset.theme === "dark" ? "light" : "dark", true);
};
try {
  const params = new URLSearchParams(location.search);
  // 默认浅色；只有手动切换过（localStorage）或显式带 ?theme= 才用深色
  const saved = params.get("theme") || localStorage.getItem(THEME_KEY);
  applyTheme(saved === "dark" ? "dark" : "light");
} catch (e) { }

// ---------- 启动 ----------
async function boot() {
  try {
    await refresh();
    const s = await api("/api/state");
    if (s.auto_key) {
      $("#btn-key").textContent = "🔑 密钥（本地自动）";
      $("#btn-key").title = "本地模拟服务不校验密钥，已自动使用占位密钥；点击可手动指定";
    }
  } catch (e) {
    toast("无法连接后端服务：" + e.message, true);
  }
}
boot();
