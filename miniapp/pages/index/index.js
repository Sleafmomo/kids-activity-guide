// 儿童兴趣班选班指南 · 主页面 —— 透明筛选逻辑，无任何推荐算法
// 数据源：../../data.js（由 scripts/build_web_data.py 从 data/*.json 生成）
const DATA = require('../../data.js');

const AB_NAME = Object.fromEntries(DATA.abilities.map(a => [a.id, a.name]));
const CAT_NAME = Object.fromEntries(DATA.categories.map(c => [c.id, c.name]));
const SRC = Object.fromEntries(DATA.sources.map(s => [s.id, s]));
const POL = Object.fromEntries(DATA.policies.map(p => [p.id, p]));
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

function fmtAge(a) {
  if (a == null) return "—";
  const whole = Math.floor(a), half = a - whole >= 0.25;
  return half ? `${whole}岁半` : `${whole}岁`;
}
function norm(s) { return (s || "").toLowerCase().replace(/\s+/g, ""); }

Page({
  data: {
    age: 5, ageText: "5岁",
    abilityChips: [], heatChips: [], categoryChips: [], policyChips: [],
    selIndoor: { names: ["不限", "室内", "户外"], values: ["any", "indoor", "outdoor"], index: 0 },
    selGroup: { names: ["不限", "团队", "个人"], values: ["any", "team", "solo"], index: 0 },
    selTempo: { names: ["不限", "大运动量", "安静型"], values: ["any", "active", "calm"], index: 0 },
    selCost: { names: ["不限", "低", "中", "高"], values: ["any", "low", "mid", "high"], index: 0 },
    familyOnly: false, search: "",
    moreOpen: false,
    eligible: [], upcoming: [], passed: [], neg: [],
    passedOpen: false,
    resultCount: "",
    showTimeline: false, timelineAge: "", timelineRows: [],
    showGuides: false,
    guides: (DATA.guides || []),
    disclaimer: "⚠ " + DATA.meta.disclaimer,
    version: `数据版本 v${DATA.meta.version} · ${DATA.meta.count} 个项目 · 本小程序为纯静态筛选，不收集任何信息`,
    showTop: false,
  },

  onLoad(options) {
    this._pendingId = options && options.id ? decodeURIComponent(options.id) : null;
    // chips 初始化
    const mk = (arr, firstAll) => {
      const out = [];
      if (firstAll) out.push({ id: "all", name: "全部", active: true });
      arr.forEach(x => out.push({ id: x.id, name: x.name, active: false }));
      return out;
    };
    this.setData({
      abilityChips: DATA.abilities.map(a => ({ id: a.id, name: a.name, active: false })),
      heatChips: [["all", "全部"], ...HEAT_ORDER.map(h => [h, HEAT_TEXT[h]])].map(([id, name], i) => ({ id, name, active: i === 0 })),
      categoryChips: mk(DATA.categories, true),
      policyChips: [["all", "全部"], ["encouraged", "官方鼓励"], ["normal", "正常"], ["caution", "⚠ 有红线"], ["neg", "✗ 负面/违规"]]
        .map(([id, name], i) => ({ id, name, active: i === 0 })),
    });
    this.render();
  },

  onReady() {
    if (this._pendingId) { this.jumpToCard(this._pendingId); this._pendingId = null; }
  },

  onPageScroll(e) {
    const show = e.scrollTop > 700;
    if (show !== this.data.showTop) this.setData({ showTop: show });
  },

  /* ---------- 筛选逻辑（透明、可解释） ---------- */
  abilityScore(a) {
    if (!state.abilities.size) return 0;
    let s = 0;
    for (const [ab, w] of Object.entries(a.abilities || {})) if (state.abilities.has(ab)) s += w;
    return s;
  },
  match(item) {
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
    const s = this.abilityScore(item);
    if (state.abilities.size && s === 0) return null;
    return s;
  },
  groupOf(a, A) {
    if (NEG.includes(a.policy) || a.age_start == null) return "neg";
    if (a.age_start <= A && (a.age_stop == null || A <= a.age_stop)) return "eligible";
    if (a.age_start > A) return "upcoming";
    return "passed";
  },

  /* ---------- 卡片视图模型 ---------- */
  buildCard(a, group) {
    const isNeg = group === "neg";
    const badge = POLICY_BADGE[a.policy];
    const A = state.age;
    let agePre = "建议 ", ageMain = fmtAge(a.age_start), ageSuf = "";
    if (group === "upcoming") {
      ageSuf = ` 开始 · 距适龄约 ${Math.max(1, Math.round((a.age_start - A) * 12))} 个月`;
    } else if (group === "passed") {
      agePre = "适龄窗口 ";
      ageMain = `${fmtAge(a.age_start)}${a.age_stop ? " - " + fmtAge(a.age_stop) : " 起"}`;
      ageSuf = "（当前年龄已过）";
    } else {
      ageSuf = a.age_stop ? ` 开始 · 适合到 ${fmtAge(a.age_stop)}` : " 开始";
    }
    const t = a.traits || {};
    const traitsLine = `${TRAIT_TEXT.indoor[t.indoor]} · ${TRAIT_TEXT.group[t.group]} · ${TRAIT_TEXT.tempo[t.tempo]} · ${TRAIT_TEXT.cost[t.cost]}${a.family_ok ? " · 在家即可" : ""}`;
    const srcs = (a.source_refs || []).map(id => SRC[id]).filter(Boolean);
    const officialRows = (a.official_support || []).map(id => POL[id]).map(p => ({
      title: `${p.title}（${p.issuer}，${p.year}）`,
      quote: p.quote || "",
      quoteSrc: p.quote ? `—— ${p.quote_src || "原文引述"}` : "",
    }));
    return {
      id: a.id, name: a.name,
      catName: CAT_NAME[a.category] || a.category,
      heatText: isNeg ? "" : (HEAT_TEXT[a.heat] || ""),
      heatCls: isNeg ? "" : `heat-${a.heat}`,
      badge: badge && a.policy !== "normal" ? badge[0] : "",
      badgeCls: badge ? badge[1] : "",
      agePre, ageMain, ageSuf,
      abs: Object.entries(a.abilities || {}).sort((x, y) => y[1] - x[1])
        .map(([id, w]) => ({ name: AB_NAME[id] || id, main: w >= 2 })),
      summary: a.summary, detail: a.detail || "", caution: a.caution || "",
      officialRows,
      note: a.note || "",
      traitsLine,
      tierText: TIER_TEXT[a.source_tier],
      tierCls: a.source_tier,
      srcText: srcs.length
        ? srcs.map(s => s.title || (s.excerpt.slice(0, 40) + "…")).join("；")
        : "暂无官方文件，为行业通行口径",
      expanded: false,
    };
  },

  render() {
    const A = state.age;
    const matched = [];
    for (const a of DATA.activities) {
      const s = this.match(a);
      if (s !== null) matched.push({ a, s });
    }
    const groups = { eligible: [], upcoming: [], passed: [], neg: [] };
    for (const { a, s } of matched) groups[this.groupOf(a, A)].push({ a, s });
    groups.eligible.sort((x, y) => y.s - x.s || x.a.age_start - y.a.age_start || x.a.name.localeCompare(y.a.name, "zh"));
    groups.upcoming.sort((x, y) => x.a.age_start - y.a.age_start);
    groups.passed.sort((x, y) => (y.a.age_stop || 99) - (x.a.age_stop || 99));
    this._lists = {
      eligible: groups.eligible.map(({ a }) => this.buildCard(a, "eligible")),
      upcoming: groups.upcoming.map(({ a }) => this.buildCard(a, "upcoming")),
      passed: groups.passed.map(({ a }) => this.buildCard(a, "passed")),
      neg: groups.neg.map(({ a }) => this.buildCard(a, "neg")),
    };
    const total = matched.length;
    this.setData({
      eligible: this._lists.eligible,
      upcoming: this._lists.upcoming,
      passed: this._lists.passed,
      neg: this._lists.neg,
      resultCount: `孩子 ${fmtAge(A)} · 符合条件 ${total} 个（适龄 ${groups.eligible.length}，不建议 ${groups.neg.length}）`,
    });
    if (this.data.showTimeline) this.renderTimeline();
  },

  /* ---------- 年龄 ---------- */
  onAgeChanging(e) { this.setData({ ageText: fmtAge(e.detail.value) }); },
  onAgeChange(e) { state.age = e.detail.value; this.setData({ age: state.age, ageText: fmtAge(state.age) }); this.render(); },
  stepAge(e) {
    const d = parseFloat(e.currentTarget.dataset.d);
    const v = Math.min(12, Math.max(3, state.age + d));
    if (v === state.age) return;
    state.age = v;
    this.setData({ age: v, ageText: fmtAge(v) });
    this.render();
  },

  /* ---------- chips / 选择器 ---------- */
  onAbility(e) {
    const id = e.currentTarget.dataset.id;
    state.abilities.has(id) ? state.abilities.delete(id) : state.abilities.add(id);
    this.setData({ abilityChips: this.data.abilityChips.map(c => c.id === id ? { ...c, active: !c.active } : c) });
    this.render();
  },
  onHeat(e) {
    const id = e.currentTarget.dataset.id;
    state.heat = id;
    this.setData({ heatChips: this.data.heatChips.map(c => ({ ...c, active: c.id === id })) });
    this.render();
  },
  onCategory(e) {
    const id = e.currentTarget.dataset.id;
    state.category = id;
    this.setData({ categoryChips: this.data.categoryChips.map(c => ({ ...c, active: c.id === id })) });
    this.render();
  },
  onPolicy(e) {
    const id = e.currentTarget.dataset.id;
    state.policy = id;
    this.setData({ policyChips: this.data.policyChips.map(c => ({ ...c, active: c.id === id })) });
    this.render();
  },
  onPick(e) {
    const key = e.currentTarget.dataset.key;
    const sel = this.data[key];
    const v = sel.values[e.detail.value];
    state[key === "selIndoor" ? "indoor" : key === "selGroup" ? "group" : key === "selTempo" ? "tempo" : "cost"] = v;
    this.setData({ [key]: { ...sel, index: e.detail.value } });
    this.render();
  },
  onFamily() {
    state.familyOnly = !state.familyOnly;
    this.setData({ familyOnly: state.familyOnly });
    this.render();
  },
  onSearch(e) {
    const v = e.detail.value;
    this.setData({ search: v });
    if (this._searchTimer) clearTimeout(this._searchTimer);
    this._searchTimer = setTimeout(() => {
      state.search = norm(v);
      this.render();
    }, 250);
  },
  onReset() {
    state.abilities.clear(); state.category = "all"; state.search = ""; state.policy = "all"; state.heat = "all";
    state.indoor = state.group = state.tempo = state.cost = "any"; state.familyOnly = false;
    state.age = 5;
    this.setData({
      age: 5, ageText: "5岁", search: "", familyOnly: false,
      abilityChips: this.data.abilityChips.map(c => ({ ...c, active: false })),
      heatChips: this.data.heatChips.map(c => ({ ...c, active: c.id === "all" })),
      categoryChips: this.data.categoryChips.map(c => ({ ...c, active: c.id === "all" })),
      policyChips: this.data.policyChips.map(c => ({ ...c, active: c.id === "all" })),
      selIndoor: { ...this.data.selIndoor, index: 0 },
      selGroup: { ...this.data.selGroup, index: 0 },
      selTempo: { ...this.data.selTempo, index: 0 },
      selCost: { ...this.data.selCost, index: 0 },
    });
    this.render();
  },

  /* ---------- 详情展开 / 分组折叠 ---------- */
  toggleDetail(e) {
    const id = e.currentTarget.dataset.id;
    for (const key of ["eligible", "upcoming", "passed", "neg"]) {
      const i = this._lists[key].findIndex(c => c.id === id);
      if (i >= 0) {
        const open = !this._lists[key][i].expanded;
        this._lists[key][i].expanded = open;
        this.setData({ [`${key}[${i}].expanded`]: open });
        return;
      }
    }
  },
  togglePassed() { this.setData({ passedOpen: !this.data.passedOpen }); },

  toggleMore() { this.setData({ moreOpen: !this.data.moreOpen }); },

  /* ---------- 时间轴 ---------- */
  toggleTimeline() {
    const show = !this.data.showTimeline;
    if (show) this.renderTimeline();
    this.setData({ showTimeline: show });
    if (show) wx.pageScrollTo({ selector: "#timeline", duration: 300 });
  },
  renderTimeline() {
    const A = state.age;
    const months = a => Math.round((a.age_start - A) * 12);
    const chip = a => ({ id: a.id, name: a.name, heatText: HEAT_TEXT[a.heat], isHot: a.heat === "hot", isRare: a.heat === "rare" });
    const elig = DATA.activities.filter(a => a.age_start != null && a.age_start <= A && (a.age_stop == null || A <= a.age_stop));
    const up = DATA.activities.filter(a => a.age_start != null && a.age_start > A);
    const now = elig.slice().sort((x, y) => (x.heat === "hot" ? -1 : 1) - (y.heat === "hot" ? -1 : 1)).slice(0, 8);
    const closing = elig.filter(a => a.age_stop != null && (a.age_stop - A) <= 0.5);
    const buckets = [
      ["现在就可以做", "d0", now.map(chip)],
      ["窗口即将关闭（半年内会过龄）", "d1", closing.map(chip)],
      ["未来 3 个月内适龄", "d2", up.filter(a => months(a) <= 3).map(chip)],
      ["3-6 个月后适龄", "d3", up.filter(a => months(a) > 3 && months(a) <= 6).map(chip)],
      ["6-12 个月后适龄", "d4", up.filter(a => months(a) > 6 && months(a) <= 12).map(chip)],
      ["更远（先了解）", "d5", []],
    ];
    this.setData({
      timelineAge: `（当前设置：${fmtAge(A)}）`,
      timelineRows: buckets.map(([label, dot, chips]) => ({
        label, dot,
        chips,
        text: chips.length ? "" : (label === "更远（先了解）"
          ? `${up.filter(a => months(a) > 12).length} 个项目适龄在一年后，点开各分类慢慢看`
          : "—"),
      })),
    });
  },
  onTimelineChip(e) { this.jumpToCard(e.currentTarget.dataset.id); },

  /* ---------- 指南 / 页脚 ---------- */
  toggleGuides() { this.setData({ showGuides: !this.data.showGuides }); },

  /* ---------- 跳转到指定项目 ---------- */
  jumpToCard(id) {
    for (const key of ["eligible", "upcoming", "passed", "neg"]) {
      const i = this._lists[key].findIndex(c => c.id === id);
      if (i >= 0) {
        this._lists[key][i].expanded = true;
        this.setData({ [`${key}[${i}].expanded`]: true });
        wx.pageScrollTo({ selector: `#item-${id}`, duration: 300 });
        return;
      }
    }
  },
  onTopTap() { wx.pageScrollTo({ scrollTop: 0, duration: 300 }); },

  /* ---------- 分享 ---------- */
  onShareAppMessage() {
    return {
      title: "儿童兴趣班选班指南 · 3-12岁家长选班筛选工具",
      path: "/pages/index/index",
    };
  },
  onShareTimeline() {
    return { title: "儿童兴趣班选班指南 · 3-12岁家长选班筛选工具" };
  },
});
