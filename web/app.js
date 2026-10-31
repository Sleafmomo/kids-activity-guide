/* 儿童兴趣班选班指南 —— 透明筛选逻辑，无任何推荐算法
   数据源：data.js（由 scripts/build_web_data.py 从 data/*.json 生成）
   功能：四组结果（含负面警示独立组）/ 项目独立链接（hash）/ 分类指南（页脚）/ 时间轴
   v1.2.2：按用户反馈移除"加入对比/复制链接"按钮与对比功能、每卡的"怎么挑"入口（指南集中在页脚） */

const AB_NAME = Object.fromEntries(DATA.abilities.map(a => [a.id, a.name]));
const CAT_NAME = Object.fromEntries(DATA.categories.map(c => [c.id, c.name]));
const SRC = Object.fromEntries(DATA.sources.map(s => [s.id, s]));
const POL = Object.fromEntries(DATA.policies.map(p => [p.id, p]));
const GUIDE = Object.fromEntries((DATA.guides || []).map(g => [g.category, g]));
const TIER_TEXT = { official: "官方文件/国标", authority: "权威机构", industry: "行业惯例" };
const HEAT_TEXT = { hot: "热门", warm: "常见", cool: "小众", rare: "稀缺" };
const HEAT_ORDER = ["hot", "warm", "cool", "rare"];
const POLICY_BADGE = {
  encouraged: ["官方鼓励", "encouraged"],
  caution: ["⚠ 有红线", "caution"],
  discouraged: ["✗ 不推荐", "negative"],
  banned_preschool: ["✗ 学龄前违规", "negative"],
  pseudoscience: ["✗ 伪科学", "negative"],
  redline: ["⛔ 绝对禁止", "negative"],
};
const TRAIT_TEXT = {
  indoor: { indoor: "室内", outdoor: "户外", both: "室内外均可" },
  group: { team: "团队", solo: "个人", both: "个人/团队均可" },
  tempo: { active: "运动量大", calm: "安静型", both: "动静兼有" },
  cost: { low: "成本低", mid: "成本中", high: "成本高" },
};
const NEG = ["discouraged", "banned_preschool", "pseudoscience", "redline"];

const state = {
  age: 5, abilities: new Set(), category: "all", search: "",
  policy: "all", heat: "all", indoor: "any", group: "any", tempo: "any", cost: "any", familyOnly: false,
};
const BY_ID = Object.fromEntries(DATA.activities.map(a => [a.id, a]));

/* ---------- 工具 ---------- */
const $ = id => document.getElementById(id);
const norm = s => (s || "").toLowerCase().replace(/\s+/g, "");
function fmtAge(a) {
  if (a == null) return "—";
  const whole = Math.floor(a), half = a - whole >= 0.25;
  return half ? `${whole}岁半` : `${whole}岁`;
}
function esc(s) { return (s || "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }

/* ---------- 筛选控件 ---------- */
function buildChips() {
  const ab = $("abilityChips");
  DATA.abilities.forEach(a => {
    const b = document.createElement("button");
    b.className = "chip"; b.textContent = a.name; b.dataset.id = a.id;
    b.onclick = () => {
      state.abilities.has(a.id) ? state.abilities.delete(a.id) : state.abilities.add(a.id);
      b.classList.toggle("active");
      render();
    };
    ab.appendChild(b);
  });
  const cat = $("categoryChips");
  [{ id: "all", name: "全部" }, ...DATA.categories].forEach(c => {
    const b = document.createElement("button");
    b.className = "chip" + (c.id === "all" ? " active" : ""); b.textContent = c.name; b.dataset.id = c.id;
    b.onclick = () => {
      state.category = c.id;
      cat.querySelectorAll(".chip").forEach(x => x.classList.toggle("active", x.dataset.id === c.id));
      render();
    };
    cat.appendChild(b);
  });
  const pol = $("policyChips");
  [["all", "全部"], ["encouraged", "官方鼓励"], ["normal", "正常"], ["caution", "⚠ 有红线"], ["neg", "✗ 负面/违规"]].forEach(([id, name], i) => {
    const b = document.createElement("button");
    b.className = "chip" + (i === 0 ? " active" : ""); b.textContent = name; b.dataset.id = id;
    b.onclick = () => {
      state.policy = id;
      pol.querySelectorAll(".chip").forEach(x => x.classList.toggle("active", x.dataset.id === id));
      render();
    };
    pol.appendChild(b);
  });
  const heat = $("heatChips");
  [["all", "全部"], ...HEAT_ORDER.map(h => [h, HEAT_TEXT[h]])].forEach(([id, name], i) => {
    const b = document.createElement("button");
    b.className = "chip" + (i === 0 ? " active" : ""); b.textContent = name; b.dataset.id = id;
    b.onclick = () => {
      state.heat = id;
      heat.querySelectorAll(".chip").forEach(x => x.classList.toggle("active", x.dataset.id === id));
      render();
    };
    heat.appendChild(b);
  });
}

function bindControls() {
  $("age").oninput = e => { state.age = parseFloat(e.target.value); $("ageValue").textContent = fmtAge(state.age); render(); };
  const stepAge = d => {
    const v = Math.min(12, Math.max(3, state.age + d));
    if (v === state.age) return;
    state.age = v; $("age").value = v; $("ageValue").textContent = fmtAge(v); render();
  };
  $("ageMinus").onclick = () => stepAge(-0.5);
  $("agePlus").onclick = () => stepAge(0.5);
  $("search").oninput = e => { state.search = norm(e.target.value); render(); };
  [["indoor", "indoor"], ["group", "group"], ["tempo", "tempo"], ["cost", "cost"]].forEach(([id, key]) => {
    $(id).onchange = e => { state[key] = e.target.value; render(); };
  });
  $("familyOnly").onchange = e => { state.familyOnly = e.target.checked; render(); };
  $("reset").onclick = () => {
    state.abilities.clear(); state.category = "all"; state.search = ""; state.policy = "all"; state.heat = "all";
    state.indoor = state.group = state.tempo = state.cost = "any"; state.familyOnly = false;
    $("age").value = 5; $("ageValue").textContent = "5岁"; state.age = 5;
    $("search").value = ""; $("familyOnly").checked = false;
    ["indoor", "group", "tempo", "cost"].forEach(id => $(id).value = "any");
    document.querySelectorAll("#abilityChips .chip").forEach(x => x.classList.remove("active"));
    document.querySelectorAll("#categoryChips .chip").forEach(x => x.classList.toggle("active", x.dataset.id === "all"));
    document.querySelectorAll("#policyChips .chip").forEach(x => x.classList.toggle("active", x.dataset.id === "all"));
    document.querySelectorAll("#heatChips .chip").forEach(x => x.classList.toggle("active", x.dataset.id === "all"));
    render();
  };
  $("timelineBtn").onclick = () => {
    const t = $("timeline");
    t.hidden = !t.hidden;
    if (!t.hidden) { renderTimeline(); t.scrollIntoView({ behavior: "smooth", block: "start" }); }
  };
  $("backTop").onclick = () => window.scrollTo({ top: 0, behavior: "smooth" });
}

/* ---------- 滚动行为：手机端下滑收起筛选区、回到顶部按钮 ---------- */
let lastY = 0, compactLockUntil = 0;
function setCompact(on) {
  const f = $("filters");
  if (f.classList.contains("compact") === on) return;
  f.classList.toggle("compact", on);
  // 收起/展开会改变页高，触发浏览器滚动锚定的反向 scroll 事件——加短冷锁防止抖动循环
  compactLockUntil = Date.now() + 350;
}
function onScroll() {
  const y = window.scrollY;
  $("backTop").hidden = y < 700;
  if (window.matchMedia("(max-width: 759px)").matches) {
    if (y < 120) setCompact(false);
    else if (Date.now() >= compactLockUntil) {
      if (y > lastY + 6 && y > 200) setCompact(true);
      else if (y < lastY - 6) setCompact(false);
    }
  } else {
    setCompact(false);
  }
  lastY = y;
}
window.addEventListener("scroll", onScroll, { passive: true });

/* ---------- 筛选逻辑（透明、可解释） ---------- */
function abilityScore(a) {
  if (!state.abilities.size) return 0;
  let s = 0;
  for (const [ab, w] of Object.entries(a.abilities || {})) if (state.abilities.has(ab)) s += w;
  return s;
}
function match(item) {
  if (state.category !== "all" && item.category !== state.category) return null;
  if (state.heat !== "all" && item.heat !== state.heat) return null;
  if (state.policy === "encouraged" && item.policy !== "encouraged") return null;
  if (state.policy === "normal" && item.policy !== "normal") return null;
  if (state.policy === "caution" && item.policy !== "caution") return null;
  if (state.policy === "neg" && !NEG.includes(item.policy)) return null;
  const t = item.traits || {};
  if (state.indoor !== "any" && t.indoor !== state.indoor && t.indoor !== "both") return null;
  if (state.group !== "any" && t.group !== state.group && t.group !== "both") return null;
  if (state.tempo !== "any" && t.tempo !== state.tempo && t.tempo !== "both") return null;
  if (state.cost !== "any" && t.cost !== state.cost) return null;
  if (state.familyOnly && !item.family_ok) return null;
  if (state.search) {
    const hay = norm(item.name + (item.aliases || []).join("") + item.summary + (CAT_NAME[item.category] || ""));
    if (!hay.includes(state.search)) return null;
  }
  const s = abilityScore(item);
  if (state.abilities.size && s === 0) return null;
  return s;
}
/* 分组：负面警示无论年龄一律进独立组；无年龄的条目只可能是警示条目 */
function groupOf(a, A) {
  if (NEG.includes(a.policy) || a.age_start == null) return "neg";
  if (a.age_start <= A && (a.age_stop == null || A <= a.age_stop)) return "eligible";
  if (a.age_start > A) return "upcoming";
  return "passed";
}

/* ---------- 渲染 ---------- */
function cardHTML(a, group) {
  const isNeg = group === "neg";
  const badge = POLICY_BADGE[a.policy];
  const badgeHTML = badge && a.policy !== "normal" ? `<span class="badge ${badge[1]}">${badge[0]}</span>` : "";
  const heatHTML = isNeg ? "" : `<span class="heat-tag heat-${a.heat}">${HEAT_TEXT[a.heat] || ""}</span>`;
  const abs = Object.entries(a.abilities || {}).sort((x, y) => y[1] - x[1])
    .map(([id, w]) => `<span class="ab-tag${w >= 2 ? " main" : ""}">${AB_NAME[id] || id}</span>`).join("");
  const t = a.traits || {};
  const traits = `环境 ${TRAIT_TEXT.indoor[t.indoor]} · ${TRAIT_TEXT.group[t.group]} · ${TRAIT_TEXT.tempo[t.tempo]} · ${TRAIT_TEXT.cost[t.cost]}${a.family_ok ? " · 在家即可" : ""}`;
  const ageLine = group === "upcoming"
    ? `建议 <b>${fmtAge(a.age_start)}</b> 开始 · 距适龄约 <b>${Math.max(1, Math.round((a.age_start - state.age) * 12))}</b> 个月`
    : group === "passed"
      ? `适龄窗口 <b>${fmtAge(a.age_start)}${a.age_stop ? " - " + fmtAge(a.age_stop) : " 起"}</b>（当前年龄已过）`
      : `建议 <b>${fmtAge(a.age_start)}</b> 开始${a.age_stop ? ` · 适合到 ${fmtAge(a.age_stop)}` : ""}`;
  const caution = a.caution ? `<div class="row warnline"><span class="k">安全提示</span><span>${esc(a.caution)}</span></div>` : "";
  const detailHTML = a.detail ? `<div class="row"><span class="k">介绍</span><span>${esc(a.detail)}</span></div>` : "";
  const note = a.note ? `<div class="row"><span class="k">补充</span><span>${esc(a.note)}</span></div>` : "";
  const official = (a.official_support || []).map(id => POL[id])
    .map(p => `<div class="row"><span class="k">✓ 官方鼓励依据</span><span>${esc(p.title)}（${esc(p.issuer)}，${p.year}）</span></div>` +
      (p.quote ? `<div class="row"><span class="k"></span><blockquote class="quote">“${esc(p.quote)}”<span class="quote-src">—— ${esc(p.quote_src || "原文引述")}</span></blockquote></div>` : "")).join("");
  const srcs = (a.source_refs || []).map(id => SRC[id]).filter(Boolean);
  const srcLine = srcs.length
    ? `<div class="row"><span class="tier ${a.source_tier}">${TIER_TEXT[a.source_tier]}</span><span>${srcs.map(s => esc(s.title || s.excerpt.slice(0, 40) + "…")).join("；")}</span></div>`
    : `<div class="row"><span class="tier ${a.source_tier}">${TIER_TEXT[a.source_tier]}</span><span>暂无官方文件，为行业通行口径</span></div>`;
  return `<article class="card ${group === "eligible" || group === "neg" ? "" : group + "-card"}" id="item-${a.id}">
    <div class="card-top">
      <a class="card-name" href="#${a.id}" title="浏览器地址栏会带 #${a.id}，转发链接可直接打开这一项">${esc(a.name)}</a>
      <span class="cat-tag">${CAT_NAME[a.category] || a.category}</span>
      ${heatHTML}
      ${badgeHTML}
    </div>
    <p class="card-age">${ageLine}</p>
    <div class="ab-tags">${abs}</div>
    <p class="card-summary">${esc(a.summary)}</p>
    <div class="card-actions">
      <button class="card-toggle" data-action="toggle" data-id="${a.id}">详情 ▾</button>
    </div>
    <div class="card-detail" id="d-${a.id}">
      ${detailHTML}${caution}${official}${note}
      <div class="row"><span class="k">形式</span><span class="traits-line">${traits}</span></div>
      ${srcLine}
    </div>
  </article>`;
}

function render() {
  const A = state.age;
  const matched = [];
  for (const a of DATA.activities) {
    const s = match(a);
    if (s !== null) matched.push({ a, s });
  }
  const groups = { eligible: [], upcoming: [], passed: [], neg: [] };
  for (const { a, s } of matched) groups[groupOf(a, A)].push({ a, s });
  groups.eligible.sort((x, y) => y.s - x.s || x.a.age_start - y.a.age_start || x.a.name.localeCompare(y.a.name, "zh"));
  groups.upcoming.sort((x, y) => x.a.age_start - y.a.age_start);
  groups.passed.sort((x, y) => y.a.age_stop - x.a.age_stop);

  $("eligibleTitle").textContent = `✓ 现在适龄 · ${groups.eligible.length} 个`;
  $("upcomingTitle").textContent = `○ 还没到年龄 · ${groups.upcoming.length} 个`;
  $("passedTitle").textContent = `– 窗口已过 · ${groups.passed.length} 个`;
  $("negTitle").textContent = `✗ 不建议 · ${groups.neg.length} 个（无论几岁）`;
  $("eligibleCards").innerHTML = groups.eligible.map(({ a }) => cardHTML(a, "eligible")).join("");
  $("upcomingCards").innerHTML = groups.upcoming.map(({ a }) => cardHTML(a, "upcoming")).join("");
  $("passedCards").innerHTML = groups.passed.map(({ a }) => cardHTML(a, "passed")).join("");
  $("negCards").innerHTML = groups.neg.map(({ a }) => cardHTML(a, "neg")).join("");
  $("upcomingGroup").style.display = groups.upcoming.length ? "" : "none";
  $("passedGroup").style.display = groups.passed.length ? "" : "none";
  $("negGroup").style.display = groups.neg.length ? "" : "none";
  const total = groups.eligible.length + groups.upcoming.length + groups.passed.length + groups.neg.length;
  $("empty").hidden = total > 0;
  $("resultCount").textContent =
    `孩子 ${fmtAge(A)} · 符合条件 ${total} 个（适龄 ${groups.eligible.length}，不建议 ${groups.neg.length}）`;
  if (!$("timeline").hidden) renderTimeline();
}

/* ---------- 事件委托（卡片按钮） ---------- */
document.addEventListener("click", e => {
  const el = e.target.closest("[data-action]");
  if (!el) return;
  if (el.dataset.action === "toggle") {
    const id = el.dataset.id;
    const d = $(`d-${id}`);
    const open = d.classList.toggle("open");
    el.textContent = open ? "收起 ▴" : "详情 ▾";
    const card = $("item-" + id);
    if (card) card.classList.toggle("expanded", open);
  }
});

/* ---------- 独立链接（hash） ---------- */
function openFromHash() {
  const id = decodeURIComponent(location.hash.slice(1));
  if (!id || !BY_ID[id]) return;
  const a = BY_ID[id];
  const d = $(`d-${id}`);
  const btn = document.querySelector(`[data-action="toggle"][data-id="${id}"]`);
  if (d && !d.classList.contains("open")) { d.classList.add("open"); if (btn) btn.textContent = "收起 ▴"; }
  const card = $(`item-${id}`);
  if (card) {
    card.classList.add("expanded");
    card.scrollIntoView({ behavior: "smooth", block: "center" });
    card.classList.add("flash");
    setTimeout(() => card.classList.remove("flash"), 2000);
  }
}
window.addEventListener("hashchange", openFromHash);

/* ---------- 分类"怎么挑"指南（页脚集中展示） ---------- */
function guideHTML(g) {
  return `<div class="guide">
    <h3>${esc(g.title)}</h3>
    <p class="guide-intro">${esc(g.intro)}</p>
    <p class="guide-h">怎么选：</p><ul>${g.points.map(p => `<li>${esc(p)}</li>`).join("")}</ul>
    <p class="guide-h">红线：</p><p class="guide-red">⚠ ${esc(g.redline)}</p>
    <p class="guide-h">花费参考：</p><p class="dim">${esc(g.budget)}（各地差异大，仅作量级参考）</p>
  </div>`;
}

/* ---------- 时间轴 ---------- */
function renderTimeline() {
  const A = state.age;
  $("tlAge").textContent = `（当前设置：${fmtAge(A)}）`;
  const months = a => Math.round((a.age_start - A) * 12);
  const elig = DATA.activities.filter(a => a.age_start != null && a.age_start <= A && (a.age_stop == null || A <= a.age_stop));
  const up = DATA.activities.filter(a => a.age_start != null && a.age_start > A);
  const chip = a => `<a class="tl-chip heat-b-${a.heat}" href="#${a.id}">${esc(a.name)}<i>${HEAT_TEXT[a.heat]}</i></a>`;
  const now = elig.slice().sort((x, y) => (x.heat === "hot" ? -1 : 1) - (y.heat === "hot" ? -1 : 1)).slice(0, 8);
  const closing = elig.filter(a => a.age_stop != null && (a.age_stop - A) <= 0.5);
  const buckets = [
    ["现在就可以做", now.length ? now.map(chip).join("") : "—"],
    ["窗口即将关闭（半年内会过龄）", closing.length ? closing.map(chip).join("") : "—"],
    ["未来 3 个月内适龄", up.filter(a => months(a) <= 3).map(chip).join("") || "—"],
    ["3-6 个月后适龄", up.filter(a => months(a) > 3 && months(a) <= 6).map(chip).join("") || "—"],
    ["6-12 个月后适龄", up.filter(a => months(a) > 6 && months(a) <= 12).map(chip).join("") || "—"],
    ["更远（先了解）", `${up.filter(a => months(a) > 12).length} 个项目适龄在一年后，点开各分类慢慢看`],
  ];
  $("timelineBody").innerHTML = buckets.map(([label, chips], i) =>
    `<div class="tl-row"><div class="tl-label"><span class="tl-dot d${i}"></span>${label}</div><div class="tl-chips">${chips}</div></div>`).join("");
}

/* ---------- 页脚 ---------- */
function renderFooter() {
  $("disclaimer").textContent = "⚠ " + DATA.meta.disclaimer;
  $("version").textContent =
    `数据版本 v${DATA.meta.version}（${DATA.meta.generated_at} 生成）· ${DATA.meta.count} 个项目 · 本页为纯静态筛选，不收集任何信息`;
  $("guideList").innerHTML = (DATA.guides || []).map(g => guideHTML(g)).join("<hr class='guide-hr'>");
  $("policyList").innerHTML = "<h3>官方文件（鼓励与约束依据）</h3>" + DATA.policies.map(p =>
    `<p class="policy-item"><b>${esc(p.title)}</b>（${esc(p.issuer)}，${p.year}${p.code ? "，" + esc(p.code) : ""}）—— ${esc(p.gist)}${p.quote ? `<blockquote class="quote">“${esc(p.quote)}”<span class="quote-src">—— ${esc(p.quote_src || "原文引述")}</span></blockquote>` : ""}</p>`).join("");
  $("sourceList").innerHTML = `<h3>信源清单（${DATA.sources.length} 条）</h3>` + DATA.sources.map(s => {
    const url = s.url ? ` <a href="${esc(s.url)}" target="_blank" rel="noopener">原文↗</a>` : "";
    return `<p class="source-item">[${s.id.toUpperCase()}] <b>${esc(s.title || "（详见摘记）")}</b>（${TIER_TEXT[s.tier]}）${esc(s.excerpt)}${url}</p>`;
  }).join("");
}

/* ---------- 启动 ---------- */
buildChips();
bindControls();
$("stats").textContent =
  `${DATA.meta.count} 个项目 · ${DATA.categories.length} 大类 · 官方鼓励 ${DATA.activities.filter(a => a.policy === "encouraged").length} 项 · 红线/负面口径如实标注`;
render();
renderFooter();
openFromHash();
