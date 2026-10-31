#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从《儿童兴趣班全景清单（权威修订版）》HTML 提取结构化数据。

数据血缘：原始 HTML（私人定制版，2026-10-23 第2版）
  → 本脚本自动提取（项目/年龄/推荐意见/理由/信源）
  → 合并 ENRICH 人工字段（能力标签/特征/政策/提示/简介）
  → data/*.json

重跑：python3 scripts/extract_from_html.py
"""
import json
import os
import re
import sys
from html.parser import HTMLParser

HTML_PATH = "/Users/sleaf/WorkBuddy/2026-10-23-13-50-41/儿童兴趣班全景清单_权威修订版_副本.html"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
TODAY = "2026-10-31"

# ---------------------------------------------------------------- 分类 / 词表

CATEGORIES = [
    {"id": "ball",    "name": "球类运动",       "slug": "球类"},
    {"id": "water",   "name": "水上运动",       "slug": "水上"},
    {"id": "ice",     "name": "冰上/雪上",      "slug": "冰雪"},
    {"id": "fitness", "name": "体能/极限/新兴", "slug": "体能"},
    {"id": "combat",  "name": "搏击/对抗/射术", "slug": "搏击"},
    {"id": "mind",    "name": "智力/思维/科技", "slug": "智力"},
    {"id": "music",   "name": "音乐",           "slug": "音乐"},
    {"id": "dance",   "name": "舞蹈",           "slug": "舞蹈"},
    {"id": "drama",   "name": "戏剧/表演/语言", "slug": "戏剧"},
    {"id": "art",     "name": "美术/手工",      "slug": "美术"},
    {"id": "nature",  "name": "自然/营地/户外", "slug": "自然"},
    {"id": "life",    "name": "生活技能/其他",  "slug": "生活"},
]

ABILITIES = [
    {"id": "physical",   "name": "体能协调", "guide_domain": "健康",
     "desc": "力量、耐力、平衡、柔韧、手眼协调等身体素质"},
    {"id": "resilience", "name": "勇气抗挫", "guide_domain": "健康·社会",
     "desc": "胆量、坚持、面对失败与困难的韧性"},
    {"id": "focus",      "name": "专注力", "guide_domain": "健康·科学",
     "desc": "注意力集中与持续、静定能力"},
    {"id": "logic",      "name": "逻辑思维", "guide_domain": "科学",
     "desc": "计算、推理、策略、观察分类等理性思维"},
    {"id": "creativity", "name": "创造力", "guide_domain": "艺术·科学",
     "desc": "想象力和创造性表达"},
    {"id": "aesthetic",  "name": "艺术审美", "guide_domain": "艺术",
     "desc": "美的感受力与艺术表现力"},
    {"id": "expression", "name": "语言表达", "guide_domain": "语言",
     "desc": "口语表达、朗读、当众表现"},
    {"id": "social",     "name": "社交协作", "guide_domain": "社会",
     "desc": "团队合作、规则意识、人际互动"},
    {"id": "hands_on",   "name": "动手实践", "guide_domain": "科学",
     "desc": "手部精细动作、操作与制作能力"},
]

# 信源分级：official=官方文件/国标；authority=权威机构/学术经典/权威媒体引专业意见；industry=行业惯例
SOURCE_TIER = {
    "r1": "official",   # 教育部《3-6岁儿童学习与发展指南》
    "r2": "authority",  # AAP 蹦床政策声明
    "r3": "authority",  # AAP 官网蹦床科普
    "r4": "official",   # 中办国办 双减意见
    "r5": "official",   # 教育部提案答复
    "r6": "authority",  # AAP 游泳课
    "r7": "authority",  # AAP 游戏的力量
    "r8": "authority",  # AAP 运动专项化
    "r9": "authority",  # 学龄前儿童运动指南（专家共识）
    "r10": "authority", # WHO 5岁以下活动指南
    "r11": "authority", # 罗恩菲德绘画六阶段
    "r13": "authority", # 人民网健康 轮滑年龄
    "r14": "official",  # 国标 GB 19079.23 蹦床场所
    "r15": "authority", # 消费者报+体操中心 蹦床
    "r16": "official",  # 卡丁车强制国标（新民晚报调查引）
    "r17": "official",  # 卫健委 户外2小时近视防控
    "r18": "industry",  # 器乐启蒙年龄行业共识
    "r19": "authority", # AAP 拳箱政策声明
    "r20": "authority", # 央广网 舞蹈下腰年龄
    "r21": "official",  # 教育部指南家长宣传册
    "r22": "authority", # 央视网 珠心算
    "r23": "authority", # 中新网 珠心算
    "r24": "official",  # 教育部点名全脑开发
    "r25": "official",  # 督导办查处量子速读
    "r26": "authority", # 科普中国 伪科学定性
    "r27": "authority", # 人民日报 感统训练
    "r28": "authority", # 央广网 感统失调
    "r29": "official",  # 国家学生体质健康标准
    "r30": "authority", # 人民日报 跳绳报班
    "r31": "authority", # 光明日报 素描不宜过早学
}

TIER_RANK = {"official": 3, "authority": 2, "industry": 1}

# ---------------------------------------------------------------- HTML 解析

class ListParser(HTMLParser):
    """提取 12 个 section 的表格行 + 文末信源清单。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.sections = []       # [{title, rows:[...]}]
        self.refs = []           # [{id, title, text, url}]
        self._buf = []           # 文本缓冲
        self._sec = None
        self._in_h2 = False
        self._in_cnt = False
        self._row = None
        self._td_slot = None     # item/age/badge/why/src
        self._td_buf = []
        self._badge_cls = None
        self._in_chg = False
        self._in_sup = False
        self._li = None
        self._in_b = False

    # ---- helpers
    def _flush(self):
        text = "".join(self._buf)
        self._buf = []
        return re.sub(r"\s+", " ", text).strip()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class", "")
        if tag == "h2":
            self._in_h2 = True
        elif tag == "h2" and False:
            pass
        elif self._in_h2 and tag == "span" and "cnt" in cls.split():
            self._in_cnt = True
        elif tag == "tr":
            self._row = {"name": "", "chg": "", "age": "", "badge": "",
                         "badge_text": "", "why": "", "src": "", "refs": []}
            self._td_slot = None
        elif tag == "td" and self._row is not None:
            if "item" in cls.split():
                self._td_slot = "item"
            elif "age" in cls.split():
                self._td_slot = "age"
            elif "why" in cls.split():
                self._td_slot = "why"
            elif "src" in cls.split():
                self._td_slot = "src"
            else:
                self._td_slot = "badge"
            self._td_buf = []
        elif tag == "span" and self._row is not None:
            if "chg" in cls.split():
                self._in_chg = True
                self._chg_buf = []
            elif cls.startswith("badge"):
                self._badge_cls = cls          # e.g. "badge b4"
                self._td_slot = self._td_slot or "badge"
        elif tag == "sup":
            self._in_sup = True
        elif tag == "a" and self._row is not None and self._td_slot == "src":
            m = re.search(r"#(r\d+)", a.get("href", ""))
            if m:
                self._row["refs"].append(m.group(1))
        elif tag == "li" and "refs" in self._get_ol_context(cls):
            self._li = {"id": "", "title": "", "text": "", "url": ""}
        elif tag == "li":
            self._li = {"id": "", "title": "", "text": "", "url": ""}
        if tag == "li" and a.get("id", "").startswith("r"):
            self._li["id"] = a["id"]
        if tag == "b" and self._li is not None:
            self._in_b = True
            self._li["_bbuf"] = []

    def _get_ol_context(self, cls):
        return cls  # li 无需上下文，靠 id 前缀判断

    def handle_endtag(self, tag):
        if tag == "h2":
            title = self._flush()
            if title:
                self._sec = {"title": title, "rows": []}
                self.sections.append(self._sec)
            self._in_h2 = False
        elif self._in_h2 and tag == "span" and self._in_cnt:
            self._in_cnt = False
        elif tag == "td" and self._row is not None and self._td_slot:
            text = re.sub(r"\s+", " ", "".join(self._td_buf)).strip()
            if self._td_slot == "item":
                self._row["name"] = text
            elif self._td_slot == "age":
                self._row["age"] = text
            elif self._td_slot == "why":
                self._row["why"] = text
            elif self._td_slot == "src":
                self._row["src"] = text
            self._td_slot = None
        elif tag == "span" and self._in_chg:
            self._row["chg"] = "".join(self._chg_buf).strip()
            self._in_chg = False
        elif tag == "sup":
            self._in_sup = False
        elif tag == "tr" and self._row is not None:
            if self._row.get("name"):
                self._sec["rows"].append(self._row)
            self._row = None
        elif tag == "b" and self._li is not None:
            self._li["title"] = re.sub(r"\s+", " ", "".join(self._li.pop("_bbuf", []))).strip()
            self._in_b = False
        elif tag == "li" and self._li is not None:
            self._li["text"] = self._flush()
            m = re.search(r"https?://\S+", self._li["text"])
            if m:
                self._li["url"] = m.group(0)
            if self._li["id"]:
                self.refs.append(self._li)
            self._li = None

    def handle_data(self, data):
        if self._in_h2 and not self._in_cnt and not self._in_sup:
            self._buf.append(data)
        if self._li is not None:
            if self._in_b:
                self._li.setdefault("_bbuf", []).append(data)
            else:
                self._buf.append(data)
        if self._in_chg and self._row is not None:
            self._chg_buf.append(data)
        elif self._td_slot and self._row is not None and not self._in_sup:
            self._td_buf.append(data)
        if self._td_slot == "badge" and self._row is not None and not self._in_sup:
            self._row["badge_text"] += data


def strip_chg_words(name: str) -> str:
    for w in ("已修正", "主课", "补条件", "窗口已过"):
        name = name.replace(w, "")
    return name.strip()


BADGE_TEXT_FALLBACK = "推荐"


# ---------------------------------------------------------------- ENRICH 人工字段
# key 为项目名（匹配时两侧均去除空白），逐项给出能力标签(2主1次)、特征、政策、提示、一句话简介。
E = {
 # ---- 一、球类 ----
 "篮球（幼儿班）": dict(
   id="ball-basketball", aliases=["幼儿篮球", "儿童篮球"],
   summary="团队球类入门，练跑跳投的综合协调与团队配合；低龄以游戏化拍球运球为主。",
   abilities={"physical": 2, "social": 2, "resilience": 1, "focus": 1},
   traits=dict(indoor="both", group="team", tempo="active", cost="mid"),
   caution="AAP 口径：组织性运动约 6 岁开始，6 岁前以自由玩耍为主、反对早期专项化；此前可在家庭以游戏阶梯练习（气球→滚球→沙包→拍球）。",
   note="原清单针对协调偏弱画像建议 6 岁后再报班，本条年龄口径即由此而来。"),
 "足球": dict(
   id="ball-football", aliases=["少儿足球"],
   summary="户外团队跑动量最大的入门球类，练体能、规则意识与团队配合。",
   abilities={"physical": 2, "social": 2, "resilience": 1},
   traits=dict(indoor="outdoor", group="team", tempo="active", cost="mid"),
   note="4-6 岁选游戏化课程、以自由踢玩为主，正式球队训练等 6 岁后。"),
 "短式网球": dict(
   id="ball-tennis", aliases=["网球", "少儿网球", "短式网球", "红球网球"],
   summary="策略型网拍运动（亚运大项），短式网球（海绵球/红球/小场地）是国际通行的低龄起步形式，约 6-8 岁过渡到标准球场。",
   abilities={"physical": 2, "focus": 1, "resilience": 1},
   traits=dict(indoor="both", group="solo", tempo="active", cost="mid"),
   age_start=4.5,
   note="红橙绿球分级体系（ITF Play & Stay）按年龄用球和场地，不必急着上标准场。"),
 "棒球/软式棒垒球": dict(
   id="ball-baseball", aliases=["棒球", "垒球", "软式棒垒球", "T-ball", "Teeball"],
   summary="击球接球跑垒兼具判断与数数乐趣的非接触球类，适合喜欢规则的孩子的团队启蒙。",
   abilities={"physical": 2, "social": 2, "logic": 1, "focus": 1},
   traits=dict(indoor="outdoor", group="team", tempo="active", cost="mid"),
   note="低龄以 T-ball/软式游戏化形式进行。"),
 "乒乓球": dict(
   id="ball-table-tennis", aliases=["乒乓"],
   summary="练手眼协调与反应速度的个人球类，费用低、终身可打，是协调能力的高性价比练习载体。",
   abilities={"physical": 2, "focus": 2, "resilience": 1},
   traits=dict(indoor="indoor", group="solo", tempo="active", cost="low"),
   note="小龄用短拍软球。"),
 "羽毛球": dict(
   id="ball-badminton", aliases=[],
   summary="普及度高、场地易得的挥拍类运动，练协调与耐力。",
   abilities={"physical": 2, "focus": 1, "resilience": 1},
   traits=dict(indoor="both", group="solo", tempo="active", cost="mid"),
   caution="腕肘力量与挥拍链要求高，低龄易挫败；正式训练建议 6 岁后，此前家长陪玩颠球即可。"),
 "排球": dict(
   id="ball-volleyball", aliases=["排球", "沙滩排球", "气排球"],
   summary="团队协作与位置感强的室内球类（亚运大项含室内排球与沙滩排球），垫球门槛较高。",
   abilities={"physical": 2, "social": 2, "resilience": 1},
   traits=dict(indoor="indoor", group="team", tempo="active", cost="mid"),
   note="垫球对低龄过难，8 岁后再学；低龄可用气球/软式排球过渡。"),
 "腰旗橄榄球": dict(
   id="ball-flag-football", aliases=["腰旗橄榄球", "橄榄球", "七人制橄榄球", "触式橄榄球"],
   summary="非接触形式的团队球类（亚运大项为七人制橄榄球），跑动多、战术启蒙友好；腰旗/触式是国际通行的儿童形式。",
   abilities={"physical": 2, "social": 2, "logic": 1},
   traits=dict(indoor="outdoor", group="team", tempo="active", cost="mid"),
   note="儿童阶段以腰旗/触式为主，正式身体对抗形式 8 岁后再考虑。"),
 "曲棍球/手球": dict(
   id="ball-handball", aliases=["手球", "曲棍球"],
   summary="持器械团队球类，国内少儿培训资源较少。",
   abilities={"physical": 2, "social": 2, "focus": 1},
   traits=dict(indoor="both", group="team", tempo="active", cost="mid")),
 "板球": dict(
   id="ball-cricket", aliases=[],
   summary="小众团队球类，规则与棒球相近。",
   abilities={"physical": 2, "social": 2, "focus": 1},
   traits=dict(indoor="outdoor", group="team", tempo="active", cost="mid")),
 "台球": dict(
   id="ball-billiards", aliases=["桌球"],
   summary="静态专注型球类，练计算与手部控制。",
   abilities={"focus": 2, "logic": 1, "physical": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="mid")),
 "保龄球": dict(
   id="ball-bowling", aliases=[],
   summary="娱乐向球类，顺带练数数计分，商场体验即可，不必报班。",
   abilities={"physical": 1, "logic": 1, "social": 1},
   traits=dict(indoor="indoor", group="both", tempo="calm", cost="mid"),
   family_ok=True),
 "壁球": dict(
   id="ball-squash", aliases=[],
   summary="室内挥拍类，一线城市青少年资源正在兴起。",
   abilities={"physical": 2, "focus": 1, "resilience": 1},
   traits=dict(indoor="indoor", group="solo", tempo="active", cost="mid")),
 "高尔夫": dict(
   id="ball-golf", aliases=["少儿高尔夫"],
   age_start=4,
   summary="专注与礼仪导向的户外运动，器材与场地费用高。",
   abilities={"focus": 2, "physical": 1, "social": 1},
   traits=dict(indoor="outdoor", group="solo", tempo="calm", cost="high"),
   status="active",
   note="高成本项目：场地+器材费用显著高于常规项目，网页端按成本筛选即可，无需特殊处理。"),
 "门球/地掷球": dict(
   id="ball-gateball", aliases=["地掷球"],
   summary="偏老年向项目，少儿无培训体系。",
   abilities={"physical": 1, "focus": 1},
   traits=dict(indoor="outdoor", group="team", tempo="calm", cost="low"),
   caution="不推荐的原因：门球是典型老年运动，全国几乎没有少儿培训班、同龄同伴和青少年赛事，孩子学了没有练习环境与展示出口；同类型的策略投掷兴趣用飞盘、地掷球玩法或保龄球体验替代更合适。",
   policy="discouraged"),
 # ---- 二、水上 ----
 "亲子游泳": dict(
   id="water-parent-swim", aliases=["婴儿游泳"],
   summary="0-4 岁窗口期的亲子戏水课，培养亲水性与仰漂；4 岁后直接转正规游泳课。",
   abilities={"physical": 1, "social": 1},
   traits=dict(indoor="indoor", group="solo", tempo="active", cost="mid"),
   age_start=1, age_stop=4,
   note="窗口性项目：AAP 认为 1-4 岁亲子戏水课可培养亲水与仰漂，1 岁内不建议正式游泳课。"),
 "游泳（正规课）": dict(
   id="water-swimming", aliases=["游泳", "儿童游泳", "泳课", "自由泳", "仰泳", "蛙泳", "蝶泳"],
   summary="生存技能型运动，一生受益；亚运大项含自由泳/仰泳/蛙泳/蝶泳四种泳姿，AAP 口径满 4 岁即可上正规课。",
   abilities={"physical": 2, "resilience": 2, "focus": 1},
   traits=dict(indoor="indoor", group="solo", tempo="active", cost="mid"),
   age_start=4,
   caution="选注重水生存技能（落水自救、仰漂）而非只教泳姿的机构；蛙泳为常见起步路径。绝对禁止野泳：不到无救生员的河湖水库等自然水域游泳——溺水是儿童意外死亡的首要原因之一（教育部防溺水'六不'）。"),
 "花样游泳": dict(
   id="water-artistic", aliases=["花样游泳"],
   summary="游泳基础上的韵律与造型项目，柔韧与水感并重。",
   abilities={"physical": 2, "aesthetic": 2, "resilience": 1},
   traits=dict(indoor="indoor", group="team", tempo="active", cost="mid"),
   caution="柔韧类训练注意 6 岁前不下腰劈叉的口径。"),
 "跳水": dict(
   id="water-diving", aliases=[],
   summary="高度专业化项目，基本只在体校体系内开展。",
   abilities={"physical": 2, "resilience": 2, "focus": 1},
   traits=dict(indoor="indoor", group="solo", tempo="active", cost="mid")),
 "水球": dict(
   id="water-polo", aliases=[],
   summary="游泳基础上的团队对抗项目，少儿资源稀缺。",
   abilities={"physical": 2, "social": 2, "resilience": 1},
   traits=dict(indoor="indoor", group="team", tempo="active", cost="mid")),
 "皮划艇": dict(
   id="water-kayak", aliases=[],
   summary="静水器械项目，多以营地体验形式开展。",
   abilities={"physical": 2, "resilience": 1, "focus": 1},
   traits=dict(indoor="outdoor", group="solo", tempo="active", cost="mid")),
 "桨板（SUP）": dict(
   id="water-sup", aliases=["桨板", "SUP"],
   summary="平衡与核心训练的水上项目，亲子体验佳。",
   abilities={"physical": 2, "focus": 1, "resilience": 1},
   traits=dict(indoor="outdoor", group="solo", tempo="active", cost="mid")),
 "帆船（OP级）": dict(
   id="water-sailing", aliases=["OP帆船", "帆船"],
   summary="风感与航线判断并重的海上项目，沿海城市体系成熟。",
   abilities={"physical": 2, "focus": 2, "logic": 1, "resilience": 1},
   traits=dict(indoor="outdoor", group="solo", tempo="active", cost="high")),
 "赛艇": dict(
   id="water-rowing", aliases=[],
   summary="专业运动队方向的项目，过早接触意义有限。",
   abilities={"physical": 2, "resilience": 2, "social": 2},
   traits=dict(indoor="outdoor", group="team", tempo="active", cost="high")),
 "蹼泳": dict(
   id="water-finswim", aliases=[],
   summary="小众竞技水上项目。",
   abilities={"physical": 2, "resilience": 1},
   traits=dict(indoor="indoor", group="solo", tempo="active", cost="mid")),
 "潜水（泳池体验）": dict(
   id="water-diving-exp", aliases=["泳池潜水体验"],
   summary="体验性质的水下活动，不作常规课程。",
   abilities={"physical": 1, "focus": 1},
   traits=dict(indoor="indoor", group="solo", tempo="active", cost="high"),
   family_ok=True),
 # ---- 三、冰雪 ----
 "滑冰（基础）": dict(
   id="ice-skating", aliases=["滑冰", "真冰"],
   summary="平衡型冰上运动，商场冰场即可玩，本质是平衡游戏。",
   abilities={"physical": 2, "focus": 1, "resilience": 1},
   traits=dict(indoor="indoor", group="solo", tempo="active", cost="mid"),
   note="低龄以冰上游戏为主。"),
 "双板滑雪": dict(
   id="ice-skiing", aliases=["滑雪"],
   summary="速度与控制型雪上运动，幼儿一律双板起步。",
   abilities={"physical": 2, "resilience": 2, "focus": 1},
   traits=dict(indoor="outdoor", group="solo", tempo="active", cost="high"),
   note="先亲子雪场或室内滑雪馆体验。"),
 "花样滑冰": dict(
   id="ice-figure", aliases=["花滑"],
   summary="冰上舞蹈型项目，艺术表现与身体控制并重。",
   abilities={"physical": 2, "aesthetic": 2, "resilience": 1},
   traits=dict(indoor="indoor", group="solo", tempo="active", cost="high"),
   caution="柔韧类训练 6 岁前不强行压韧带；6 岁前以玩冰为主。"),
 "冰球": dict(
   id="ice-hockey", aliases=[],
   summary="高装备、高频次的冰上团队对抗项目。",
   abilities={"physical": 2, "social": 2, "resilience": 2},
   traits=dict(indoor="indoor", group="team", tempo="active", cost="high"),
   note="先滑冰看兴趣再入坑。"),
 "短道速滑": dict(
   id="ice-shorttrack", aliases=[],
   summary="竞技体制路线项目，普通家庭不建议。",
   abilities={"physical": 2, "resilience": 2},
   traits=dict(indoor="indoor", group="solo", tempo="active", cost="high")),
 "冰壶": dict(
   id="ice-curling", aliases=[],
   summary="策略型'冰上象棋'，安静专注，但少儿资源稀缺。",
   abilities={"focus": 2, "logic": 2, "physical": 1},
   traits=dict(indoor="indoor", group="team", tempo="calm", cost="high")),
 "单板滑雪": dict(
   id="ice-snowboard", aliases=["单板"],
   summary="技巧型雪上项目，对平衡与力量要求更高。",
   abilities={"physical": 2, "resilience": 2, "creativity": 1},
   traits=dict(indoor="outdoor", group="solo", tempo="active", cost="high"),
   note="幼儿一律双板起步，单板 8 岁后。"),
 # ---- 四、体能/极限/新兴 ----
 "少儿体能/体适能": dict(
   id="fitness-kids", aliases=["体适能", "儿童体能课", "感统体能"],
   summary="跑跳攀爬攀网的综合'运动母课'，是所有专项的地基，游戏化、非专项。",
   abilities={"physical": 2, "resilience": 1, "social": 1, "focus": 1},
   traits=dict(indoor="indoor", group="team", tempo="active", cost="mid"),
   note="《学龄前儿童(3-6岁)运动指南》：运动'以愉快的游戏为主要形式''避免长时间、大强度的专业化训练'——体能课正是该口径的标准载体。"),
 "快乐体操": dict(
   id="fitness-gymnastics", aliases=["体操", "幼儿体操", "少儿体操", "竞技体操", "艺术体操",
                                     "单杠", "双杠", "跳马", "鞍马", "吊环", "高低杠", "平衡木"],
   summary="亚运/奥运大项：垫上与器械动作（单杠、双杠、跳马、平衡木等）练柔韧、平衡与身体控制；少儿以'快乐体操'游戏化课程起步。",
   abilities={"physical": 2, "focus": 1, "resilience": 1},
   traits=dict(indoor="indoor", group="both", tempo="active", cost="mid"),
   age_start=3,
   caution="选'快乐体操'类的游戏化课程；专业竞技体操训练（高强度压柔韧）是另一回事，低龄应远离。注意 6 岁前不强行压韧带、不下腰的通用红线。蹦床虽属体操分项，但风险 profile 完全不同，见蹦床条目。",
   note="国家体育总局体操运动管理中心在全国推广'快乐体操'并配套等级锻炼标准，为低龄体操的官方化路径；具体文件待下一批核实。"),
 "蹦床（娱乐/蹦床馆）": dict(
   id="fitness-trampoline", aliases=["蹦床馆", "室内蹦床"],
   summary="高刺激但受伤风险明确的项目，6 岁前不建议参与。",
   abilities={"physical": 2},
   traits=dict(indoor="indoor", group="solo", tempo="active", cost="mid"),
   policy="caution",
   caution="AAP 红线：6 岁以下儿童'永远不应'使用蹦床。6 岁后若参与：一次一人上网、严禁空翻、家长全程盯、单次≤2小时、确认场馆按国标（GB 19079.23）配安全员并投意外险。"),
 "跳绳": dict(
   id="fitness-rope", aliases=["竞速跳绳"],
   summary="小学体测必测+唯一加分项的'刚需'运动，学校会教，在家每天几分钟即可，报班无实质意义。",
   abilities={"physical": 2, "focus": 1},
   traits=dict(indoor="both", group="solo", tempo="active", cost="low"),
   family_ok=True,
   note="《国家学生体质健康标准(2014修订)》：1分钟跳绳为小学一至六年级必测，一、二年级权重20%，唯一加分指标（最多加20分）；人民日报报道专家意见：报班无实质意义。"),
 "少儿跑酷": dict(
   id="fitness-parkour", aliases=["跑酷", "儿童跑酷", "障碍赛", "斯巴达小勇士"],
   summary="跑跳攀爬翻越的游戏化场地运动，与好动孩子天性最匹配的新兴项目。",
   abilities={"physical": 2, "resilience": 2, "creativity": 1, "focus": 1},
   traits=dict(indoor="indoor", group="solo", tempo="active", cost="mid")),
 "攀岩（幼儿抱石）": dict(
   id="fitness-climbing", aliases=["抱石", "儿童攀岩"],
   summary="练胆量与问题解决的垂直运动，低难度线路是'看得见的数学题'。",
   abilities={"physical": 2, "resilience": 2, "focus": 2, "logic": 1},
   traits=dict(indoor="indoor", group="solo", tempo="active", cost="mid"),
   note="选有缓冲垫、低龄专区的场馆，慢热孩子先体验区玩。"),
 "滑板": dict(
   id="fitness-skateboard", aliases=[],
   summary="平衡与勇气型街头运动，儿童软板启蒙。",
   abilities={"physical": 2, "resilience": 2, "focus": 1},
   traits=dict(indoor="outdoor", group="solo", tempo="active", cost="mid"),
   caution="家长需接受摔倒擦伤，护具齐备。"),
 "定向越野": dict(
   id="fitness-orienteering", aliases=["定向"],
   summary="识图找点的'寻宝'运动，判断与奔跑并重，亲子形式成本低。",
   abilities={"logic": 2, "physical": 1, "focus": 2, "hands_on": 1},
   traits=dict(indoor="outdoor", group="both", tempo="active", cost="low")),
 "平衡车": dict(
   id="fitness-balance-bike", aliases=["滑步车"],
   summary="2-4 岁黄金期的平衡启蒙，本质是玩具，不必报班。",
   abilities={"physical": 2, "focus": 1},
   traits=dict(indoor="both", group="solo", tempo="active", cost="low"),
   family_ok=True,
   note="窗口性项目：4 岁后黄金期已过，仅作过渡玩具骑。"),
 "轮滑": dict(
   id="fitness-roller", aliases=["旱冰", "直排轮"],
   summary="平衡型滑行运动，对踝关节发育有明确年龄要求。",
   abilities={"physical": 2, "focus": 1, "resilience": 1},
   traits=dict(indoor="both", group="solo", tempo="active", cost="mid"),
   caution="踝关节发育原因不宜早：医学口径 4-5 岁可开始（4 岁以下有 X 型腿风险），本库采用更保守的 5.5-6 岁口径；学习时硬壳鞋+护腕护肘护膝头盔全套护具，滑 5-10 分钟休息一次。"),
 "小轮车（BMX）": dict(
   id="fitness-bmx", aliases=["BMX", "自由式小轮车", "BMX自由式", "BMX竞速"],
   summary="技巧型骑行项目（亚运大项含 BMX 竞速与自由式小轮车），对力量胆量要求高。",
   abilities={"physical": 2, "resilience": 2},
   traits=dict(indoor="outdoor", group="solo", tempo="active", cost="mid")),
 "卡丁车（儿童）": dict(
   id="fitness-karting", aliases=["卡丁车", "儿童卡丁车"],
   summary="速度兴趣的落地项目，台阶式规划：商场慢车→儿童车→教学车。",
   abilities={"focus": 2, "resilience": 2, "physical": 1, "logic": 1},
   traits=dict(indoor="indoor", group="solo", tempo="active", cost="high"),
   age_start=4.5,
   caution="2026年9月强制国标：只坐专用儿童卡丁车（拒绝成人改装车）、全盔+护目镜+护胸板一样不少、家长全程在场不上成人赛道；业内独立驾驶底线 6-7 岁/身高 1.2 米。"),
 "趣味田径": dict(
   id="fitness-athletics", aliases=["田径", "跑步", "短跑", "跳远", "跳高", "投掷", "少儿田径"],
   summary="跑、跳、投是田径（亚运/奥运大项）的三大根基，也是最基础的人类运动能力；少儿以'趣味田径'游戏化形式开展，6 岁前体能课可覆盖。",
   abilities={"physical": 2, "resilience": 1, "social": 1},
   traits=dict(indoor="both", group="team", tempo="active", cost="mid"),
   age_start=6,
   note="体能课可覆盖低龄需求；小学阶段田径是校运会与体测的核心内容，跑姿与兴趣优先于成绩。"),
 "少儿铁三": dict(
   id="fitness-triathlon", aliases=["小铁人"],
   summary="游泳+骑行+跑步的综合耐力项目，需先有单项基础。",
   abilities={"physical": 2, "resilience": 2},
   traits=dict(indoor="both", group="solo", tempo="active", cost="mid")),
 "亲子马拉松/越野": dict(
   id="fitness-family-run", aliases=["亲子跑", "欢乐跑"],
   summary="活动性质的家庭参与项目，不是课程。",
   abilities={"physical": 1, "social": 1},
   traits=dict(indoor="outdoor", group="both", tempo="active", cost="low"),
   age_start=3,
   family_ok=True),
 # ---- 五、搏击/对抗/射术 ----
 "跆拳道": dict(
   id="combat-taekwondo", aliases=["跆拳道"],
   summary="低龄友好的对抗项目入门，练规矩听指令与身体控制。",
   abilities={"physical": 2, "resilience": 2, "focus": 1, "social": 1},
   traits=dict(indoor="indoor", group="both", tempo="active", cost="mid"),
   note="低龄选品势/游戏化课程，实战对练不硬性要求。"),
 "击剑": dict(
   id="combat-fencing", aliases=["花剑", "佩剑", "重剑"],
   summary="'身体象棋'——最吃战术计算的对抗项目，非接触性（不击打头部），低龄友好度高。",
   abilities={"logic": 2, "physical": 2, "focus": 2, "resilience": 1},
   traits=dict(indoor="indoor", group="solo", tempo="active", cost="high")),
 "武术（传统）": dict(
   id="combat-wushu", aliases=["传统武术", "武术套路", "散打"],
   summary="亚运大项：套路与散打两大分项。套路形式练身体控制、记忆与礼仪，散打为对抗形式。",
   abilities={"physical": 2, "focus": 2, "resilience": 1},
   traits=dict(indoor="indoor", group="solo", tempo="active", cost="mid"),
   caution="套路形式适合低龄；散打等对抗形式建议 8 岁后，含头部击打成分，选机构时从严把关（同拳击口径方向）。"),
 "空手道": dict(
   id="combat-karate", aliases=[],
   summary="型（套路）为主的对抗项目，与跆拳道、武术同赛道。",
   abilities={"physical": 2, "resilience": 2, "focus": 1},
   traits=dict(indoor="indoor", group="solo", tempo="active", cost="mid")),
 "射箭": dict(
   id="combat-archery", aliases=[],
   summary="安静专注+弹道计算的项目，低磅数儿童弓起步。",
   abilities={"focus": 2, "physical": 1, "logic": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="mid")),
 "剑道": dict(
   id="combat-kendo", aliases=[],
   summary="礼仪与装备都偏'重'的对抗项目，适合大些的孩子。",
   abilities={"physical": 2, "focus": 2, "resilience": 1},
   traits=dict(indoor="indoor", group="both", tempo="active", cost="mid")),
 "巴西柔术": dict(
   id="combat-bjj", aliases=["柔术", "少儿柔术"],
   summary="一对一地面对抗形式温和（亚运大项含柔术 ju-jitsu 分项），以控制与降服代替击打，一线城市少儿班正在兴起。",
   abilities={"physical": 2, "resilience": 2, "logic": 1},
   traits=dict(indoor="indoor", group="both", tempo="active", cost="mid")),
 "少儿拳击": dict(
   id="combat-boxing", aliases=["拳击"],
   summary="以击打头部为得分手段的对抗项目，权威机构明确反对儿童参与。",
   abilities={"physical": 2, "resilience": 2},
   traits=dict(indoor="indoor", group="both", tempo="active", cost="mid"),
   policy="caution",
   caution="AAP 与加拿大儿科协会联合政策声明：因拳击'鼓励并奖励对头面部的故意击打'，明确反对儿童青少年参与——比'几岁可以学'更严格；若坚持对抗类兴趣，选击剑/跆拳道等非击打头部项目。"),
 "摔跤/散打": dict(
   id="combat-wrestling", aliases=["古典式摔跤", "自由式摔跤", "摔跤"],
   summary="亚运/奥运大项：古典式与自由式摔跤，力量、重心与控制的直接对话。",
   abilities={"physical": 2, "resilience": 2, "focus": 1},
   traits=dict(indoor="indoor", group="both", tempo="active", cost="mid"),
   policy="caution",
   caution="低龄以基础滚翻与体感游戏为主，正式对抗训练建议 8 岁后；选有保护规则、裁判和护具的机构。（注：散打属武术分项，已移至武术条目。）"),
 "太极": dict(
   id="combat-taichi", aliases=["太极拳"],
   summary="跟长辈晨练就能玩的低强度运动。",
   abilities={"physical": 1, "focus": 1},
   traits=dict(indoor="both", group="solo", tempo="calm", cost="low"),
   family_ok=True),
 "射击（激光/模拟）": dict(
   id="combat-laser-shot", aliases=["激光射击", "模拟射击", "射击", "飞碟射击", "气步枪"],
   summary="亚运/奥运大项；儿童以激光枪/模拟体验形式入门，练静态专注与情绪稳定。",
   abilities={"focus": 2, "logic": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="mid")),
 # ---- 六、智力/思维/科技 ----
 "围棋": dict(
   id="mind-go", aliases=["学围棋"],
   summary="规则极简、计算极深的经典棋类，顺带练专注与抗挫。",
   abilities={"logic": 2, "focus": 2, "resilience": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="low"),
   note="可先五子棋/家庭桌游过渡试探兴趣。"),
 "乐高建构课": dict(
   id="mind-lego", aliases=["积木课", "乐高课", "大颗粒", "机械搭建"],
   summary="空间与动手兴趣的最优载体，开放材料优于程式化教学。",
   abilities={"hands_on": 2, "creativity": 2, "logic": 1, "focus": 1},
   traits=dict(indoor="indoor", group="both", tempo="calm", cost="mid"),
   note="属非学科类（科技类）培训，不在双减禁止范围。"),
 "魔方": dict(
   id="mind-rubik", aliases=["复原魔方"],
   summary="几十块成本的逻辑玩具，成就感来得快，在家教即可。",
   abilities={"logic": 2, "hands_on": 1, "focus": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="low"),
   family_ok=True),
 "国际象棋": dict(
   id="mind-chess", aliases=["国象"],
   summary="战术计算型棋类，与围棋二选一。",
   abilities={"logic": 2, "focus": 2, "resilience": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="low")),
 "中国象棋": dict(
   id="mind-xiangqi", aliases=["象棋"],
   summary="规则亲民、祖辈即可陪练的棋类。",
   abilities={"logic": 2, "focus": 2, "resilience": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="low"),
   family_ok=True),
 "科学实验课": dict(
   id="mind-science", aliases=["科学课", "STEM课", "趣味科学", "科学启蒙"],
   summary="动手派兴趣启蒙，直接对接官方'科学探究'培养目标。",
   abilities={"hands_on": 2, "logic": 2, "creativity": 1},
   traits=dict(indoor="indoor", group="both", tempo="calm", cost="mid")),
 "天文观测": dict(
   id="mind-astronomy", aliases=["观星"],
   summary="不是班是爱好：入门望远镜+认星座，对分类和规律敏感的孩子天然着迷。",
   abilities={"logic": 2, "focus": 1, "hands_on": 1},
   traits=dict(indoor="outdoor", group="both", tempo="calm", cost="low"),
   family_ok=True),
 "财商启蒙": dict(
   id="mind-financial", aliases=["理财启蒙"],
   summary="数钱付账、零花钱记账——数字敏感期的应用题，在家玩即可。",
   abilities={"logic": 1, "hands_on": 1, "focus": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="low"),
   family_ok=True),
 "数独（儿童版）": dict(
   id="mind-sudoku", aliases=["数独"],
   summary="印刷版+APP 即可玩的逻辑游戏。",
   abilities={"logic": 2, "focus": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="low"),
   family_ok=True),
 "速叠杯": dict(
   id="mind-stacking", aliases=["竞技叠杯"],
   summary="手速游戏，顺带练精细动作，在家玩。",
   abilities={"hands_on": 1, "focus": 1, "physical": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="low"),
   family_ok=True),
 "五子棋": dict(
   id="mind-gomoku", aliases=[],
   summary="棋类兴趣的最低门槛试金石。",
   abilities={"logic": 2, "focus": 1},
   traits=dict(indoor="indoor", group="both", tempo="calm", cost="low"),
   family_ok=True),
 "国际跳棋": dict(
   id="mind-checkers", aliases=["国跳"],
   summary="规则简单计算深的棋类，有资源可试。",
   abilities={"logic": 2, "focus": 1},
   traits=dict(indoor="indoor", group="both", tempo="calm", cost="low")),
 "地图/地理爱好": dict(
   id="mind-geography", aliases=["地理"],
   summary="认路认地标的日常游戏，在家玩。",
   abilities={"logic": 1, "hands_on": 1, "focus": 1},
   traits=dict(indoor="both", group="solo", tempo="calm", cost="low"),
   family_ok=True),
 "车模/拼装模型": dict(
   id="mind-model-vehicles", aliases=["拼装模型", "车模", "高达", "拼装高达"],
   summary="从大颗粒到小颗粒的专注力训练，与机械兴趣联动。",
   abilities={"hands_on": 2, "focus": 2, "creativity": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="mid"),
   family_ok=True),
 "航模": dict(
   id="mind-aero-model", aliases=["航空模型"],
   summary="动手+空气动力学的组合，先拼装静态模型过渡。",
   abilities={"hands_on": 2, "logic": 1, "focus": 1, "creativity": 1},
   traits=dict(indoor="both", group="solo", tempo="calm", cost="mid")),
 "海模/船模": dict(
   id="mind-ship-model", aliases=["船模", "航海模型"],
   summary="小众但气质对口的动手项目。",
   abilities={"hands_on": 2, "logic": 1, "focus": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="mid")),
 "无人机": dict(
   id="mind-drone", aliases=["航拍无人机", "编程无人机", "无人机竞赛"],
   summary="操作门槛+法规年龄限制都明确的项目。",
   abilities={"hands_on": 2, "logic": 1, "focus": 2},
   traits=dict(indoor="both", group="solo", tempo="calm", cost="high"),
   caution="注意无人机操作的相关法规年龄限制。"),
 "机器人启蒙": dict(
   id="mind-robotics", aliases=["机器人课", "乐高机器人", "EV3", "SPIKE", "VEX", "FLL", "WRO", "机器人竞赛"],
   summary="乐高建构的自然下一步，机械+编程启蒙。",
   abilities={"hands_on": 2, "logic": 2, "creativity": 1},
   traits=dict(indoor="indoor", group="both", tempo="calm", cost="mid")),
 "图形化编程（Scratch）": dict(
   id="mind-scratch", aliases=["Scratch", "编程启蒙"],
   summary="拖拽积木式的编程启蒙，识字量够了再上，别被焦虑营销带跑。",
   abilities={"logic": 2, "creativity": 2, "focus": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="mid"),
   caution="需一定识字量，一般 6-7 岁起步。"),
 "少儿编程（代码级）": dict(
   id="mind-coding", aliases=["Python少儿编程", "代码编程", "C++", "信息学奥赛", "信奥赛", "CSP-J"],
   summary="真正的代码学习，抽象思维成熟前（约 9 岁）学意义有限。",
   abilities={"logic": 2, "focus": 2, "creativity": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="mid")),
 "珠心算": dict(
   id="mind-abacus", aliases=["珠算", "心算"],
   summary="官方未禁但专家共识负面：与小学竖式教学冲突，弊大于利。",
   abilities={"logic": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="mid"),
   policy="discouraged",
   caution="学龄前儿童以具体形象思维为主，珠心算的抽象运算法则与其认知规律相悖；学过的孩子入学后'先想算盘再算题'，与竖式教学冲突（央视网/中新网引学前教育专家与脑科学研究者口径）。"),
 "幼小衔接班/思维训练班": dict(
   id="mind-preschool-academic", aliases=["幼小衔接", "思维训练班", "学前班", "拼音班", "识字班"],
   summary="以小学化教学招揽学龄前儿童的培训班，教育部明令禁止的违规办学形式，直接排除即可。",
   abilities={},
   traits=dict(indoor="indoor", group="both", tempo="calm", cost="mid"),
   age_start=3, age_stop=6,
   policy="banned_preschool",
   refs=["r4", "r5"],
   caution="双减文件原文：'严禁以学前班、幼小衔接班、思维训练班等名义面向学龄前儿童开展线下学科类（含外语）培训''不得开展面向学龄前儿童的线上培训'；幼儿园'小学化'治理同步推进（教育部官网答复确认）。幼小衔接的正确方式是习惯与能力准备，不是提前上课。"),
 "全脑开发/右脑/记忆法": dict(
   id="mind-right-brain", aliases=["全脑开发", "右脑开发", "量子速读", "记忆法"],
   summary="伪科学重灾区，唯一不需要试听就能排除的类别。",
   abilities={},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="mid"),
   policy="pseudoscience",
   caution="教育部点名'全脑开发''右脑开发''量子速读'为'贩卖概念、似是而非的教育理论'；国务院教育督导办曾查处关停相关违规机构；中国科协科普中国定性为伪科学骗局。"),
 # ---- 七、音乐 ----
 "奥尔夫音乐启蒙": dict(
   id="music-orff", aliases=["奥尔夫", "音乐启蒙课"],
   summary="器乐前的正确过渡：团体游戏形式的音乐启蒙。",
   abilities={"aesthetic": 2, "social": 1, "expression": 1, "focus": 1},
   traits=dict(indoor="indoor", group="team", tempo="calm", cost="mid"),
   note="行业共识：3-4 岁仅奥尔夫/亲子音乐游戏，5-6 岁为器乐黄金期。"),
 "非洲鼓": dict(
   id="music-djembe", aliases=["金贝鼓", "非洲鼓课"],
   summary="门槛低、动静大的节奏乐器，适合先建立节奏感。",
   abilities={"aesthetic": 2, "focus": 1, "hands_on": 1},
   traits=dict(indoor="indoor", group="both", tempo="active", cost="mid")),
 "尤克里里": dict(
   id="music-ukulele", aliases=["乌克丽丽"],
   summary="乐器里最轻的入门，成就感来得快。",
   abilities={"aesthetic": 2, "hands_on": 1, "focus": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="low")),
 "钢琴": dict(
   id="music-piano", aliases=["学钢琴", "电钢琴"],
   summary="乐器学习的'标准起点'，5-6 岁为黄金启蒙期。",
   abilities={"aesthetic": 2, "focus": 2, "hands_on": 1, "resilience": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="high"),
   note="先奥尔夫一年过渡更稳；学琴找老师比找机构重要，家长陪练是成败关键。"),
 "小提琴（铃木教学）": dict(
   id="music-violin", aliases=["小提琴", "铃木小提琴", "中提琴"],
   summary="唯一接受低龄（4-5 岁）的器乐体系，但需家长全程陪练、投入大。",
   abilities={"aesthetic": 2, "focus": 2, "hands_on": 1, "resilience": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="high")),
 "爵士鼓": dict(
   id="music-drums", aliases=["架子鼓", "爵士鼓"],
   summary="精力旺盛孩子的节奏出口，注意手腕负荷与音量护耳。",
   abilities={"aesthetic": 2, "physical": 1, "focus": 1},
   traits=dict(indoor="indoor", group="solo", tempo="active", cost="high"),
   caution="注意护耳（长期高分贝）与手腕负荷。"),
 "童声声乐": dict(
   id="music-vocal", aliases=["唱歌课", "声乐", "说唱", "说唱启蒙"],
   summary="以兴趣唱为主，变声前不作专业发声训练。",
   abilities={"aesthetic": 2, "expression": 2},
   traits=dict(indoor="indoor", group="both", tempo="calm", cost="mid")),
 "二胡": dict(
   id="music-erhu", aliases=[],
   summary="民乐里门槛较低的拉弦乐器。",
   abilities={"aesthetic": 2, "hands_on": 1, "focus": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="low")),
 "古筝": dict(
   id="music-guzheng", aliases=[],
   summary="入门快的常见民乐选择。",
   abilities={"aesthetic": 2, "hands_on": 1, "focus": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="mid")),
 "竹笛/葫芦丝": dict(
   id="music-dizi", aliases=["笛子", "葫芦丝"],
   summary="便宜、便携的吹奏民乐。",
   abilities={"aesthetic": 2, "hands_on": 1, "expression": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="low")),
 "琵琶": dict(
   id="music-pipa", aliases=[],
   summary="指法要求较高的民乐器。",
   abilities={"aesthetic": 2, "hands_on": 1, "focus": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="mid")),
 "大提琴": dict(
   id="music-cello", aliases=[],
   summary="有儿童分级尺寸的弦乐器。",
   abilities={"aesthetic": 2, "hands_on": 1, "focus": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="high")),
 "古典吉他": dict(
   id="music-guitar", aliases=["吉他"],
   summary="可先尤克里里过渡的拨弦乐器。",
   abilities={"aesthetic": 2, "hands_on": 1, "focus": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="mid")),
 "长笛/黑管等管乐": dict(
   id="music-wind", aliases=["长笛", "黑管", "管乐", "单簧管", "双簧管", "大管", "巴松"],
   summary="音色优美的管乐器，但对牙齿口腔发育有硬性要求。",
   abilities={"aesthetic": 2, "hands_on": 1, "focus": 1},
   traits=dict(indoor="indoor", group="both", tempo="calm", cost="mid"),
   caution="行业共识：管乐须等换牙完成（约 7-9 岁）再学。"),
 "小号/铜管": dict(
   id="music-brass", aliases=["小号", "铜管", "圆号", "长号", "大号"],
   summary="对肺活量与恒牙都有要求的铜管乐器。",
   abilities={"aesthetic": 2, "physical": 1, "hands_on": 1},
   traits=dict(indoor="indoor", group="both", tempo="calm", cost="mid")),
 "合唱团": dict(
   id="music-choir", aliases=["合唱"],
   summary="集体音乐形式，练听觉、协作与纪律。",
   abilities={"aesthetic": 2, "expression": 2, "social": 2},
   traits=dict(indoor="indoor", group="team", tempo="calm", cost="low"),
   note="有识字与集体纪律要求，一般 6 岁后。"),
 "音乐制作/编曲": dict(
   id="music-production", aliases=["编曲", "电子音乐", "DJ"],
   summary="数字时代的'新乐器'，需乐理底子。",
   abilities={"aesthetic": 2, "creativity": 2, "logic": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="mid")),
 # ---- 八、舞蹈 ----
 "街舞（启蒙）": dict(
   id="dance-street", aliases=["街舞", "少儿街舞", "霹雳舞", "Breaking"],
   summary="律动+胆量的舞蹈入门，无下腰劈叉类动作风险；霹雳舞（Breaking）已是亚运/奥运正式项目，属街舞大类的竞技形式。",
   abilities={"physical": 1, "aesthetic": 2, "expression": 1, "resilience": 1},
   traits=dict(indoor="indoor", group="both", tempo="active", cost="mid"),
   note="慢热孩子可选小班慢节奏课堂。"),
 "中国舞": dict(
   id="dance-chinese", aliases=["民族舞"],
   summary="练体态与听指令的经典舞种，低龄只上兴趣启蒙班。",
   abilities={"physical": 1, "aesthetic": 2, "expression": 1, "resilience": 1},
   traits=dict(indoor="indoor", group="both", tempo="active", cost="mid"),
   caution="4.5-6 岁只上兴趣启蒙班：不下腰、不劈叉、不倒立；专业训练建议 7 岁后，防止脊柱与腰椎损伤（儿童骨科/康复口径）。"),
 "芭蕾启蒙": dict(
   id="dance-ballet", aliases=["芭蕾"],
   summary="被低估的'体态+纪律'课，男孩学舞完全正常；低龄以地面/把杆游戏化内容为主。",
   abilities={"physical": 1, "aesthetic": 2, "expression": 1, "focus": 1},
   traits=dict(indoor="indoor", group="both", tempo="active", cost="mid"),
   caution="6 岁前不下腰劈叉、严禁足尖训练。",
   gender_note="男孩学芭蕾完全正常，无需因性别排除。"),
 "拉丁舞": dict(
   id="dance-latin", aliases=[],
   summary="节奏外放的舞蹈，看孩子律动偏好。",
   abilities={"physical": 1, "aesthetic": 2, "expression": 1},
   traits=dict(indoor="indoor", group="both", tempo="active", cost="mid"),
   caution="柔韧训练注意 6 岁前口径。"),
 "爵士舞": dict(
   id="dance-jazz", aliases=["韩舞", "Kpop编舞", "爵士舞课"],
   summary="街舞的近亲，风格不同。",
   abilities={"physical": 1, "aesthetic": 2, "expression": 1},
   traits=dict(indoor="indoor", group="both", tempo="active", cost="mid")),
 "现代舞/国标": dict(
   id="dance-modern", aliases=["现代舞", "国标"],
   summary="需要基础舞感后再进入的舞种。",
   abilities={"physical": 1, "aesthetic": 2, "expression": 1},
   traits=dict(indoor="indoor", group="both", tempo="active", cost="mid")),
 "踢踏舞": dict(
   id="dance-tap", aliases=["踢踏"],
   summary="节奏感极强者的菜。",
   abilities={"aesthetic": 2, "physical": 1, "focus": 1},
   traits=dict(indoor="indoor", group="both", tempo="active", cost="mid")),
 # ---- 九、戏剧/表演/语言 ----
 "儿童戏剧/绘本剧": dict(
   id="drama-drama", aliases=["儿童剧", "绘本剧", "戏剧课"],
   summary="被低估的'表达+共情+当众表现'课，本质是假装游戏的教学化延伸，慢热孩子的脱敏课。",
   abilities={"expression": 2, "social": 2, "creativity": 2, "focus": 1},
   traits=dict(indoor="indoor", group="team", tempo="active", cost="mid")),
 "口才/小主持人": dict(
   id="drama-speech", aliases=["小主持人", "口才课", "讲故事", "小小讲解员"],
   summary="练胆量与当众表达的口语课程。",
   abilities={"expression": 2, "focus": 1, "social": 1},
   traits=dict(indoor="indoor", group="both", tempo="calm", cost="mid"),
   note="选游戏化课堂，避免过早背诵式表演。"),
 "朗诵": dict(
   id="drama-recitation", aliases=["朗诵课"],
   summary="比口才更'文'的语言艺术形式。",
   abilities={"expression": 2, "focus": 1, "aesthetic": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="low")),
 "英语启蒙": dict(
   id="drama-english", aliases=["英语班", "英语启蒙课", "磨耳朵", "英文儿歌", "英语动画"],
   summary="语音敏感期在家磨耳朵（儿歌+动画+亲子绘本）完全可行且零风险；任何面向学龄前孩子的英语班均属违规办学。",
   abilities={"expression": 1, "logic": 1},
   traits=dict(indoor="indoor", group="both", tempo="calm", cost="low"),
   policy="banned_preschool",
   family_ok=True,
   caution="双减文件原文：'严禁以学前班、幼小衔接班、思维训练班等名义面向学龄前儿童开展线下学科类（含外语）培训''不得开展面向学龄前儿童的线上培训'——违规机构被查处/跑路风险高，报班即踩雷；在家磨耳朵不受影响。"),
 "相声/快板": dict(
   id="drama-crosstalk", aliases=["快板", "相声"],
   summary="传统文化+语言节奏的曲艺形式。",
   abilities={"expression": 2, "focus": 1, "aesthetic": 1},
   traits=dict(indoor="indoor", group="both", tempo="calm", cost="low")),
 "京剧（行当启蒙）": dict(
   id="drama-jingju", aliases=["京剧", "戏曲"],
   summary="唱念做打练身段气息，非常练专注与身体控制；真入门要走科班路，先体验。",
   abilities={"expression": 2, "aesthetic": 2, "physical": 1, "focus": 1},
   traits=dict(indoor="indoor", group="both", tempo="active", cost="mid")),
 "秦腔（本地戏种）": dict(
   id="drama-qinqiang", display_name="戏曲（地方剧种）",
   aliases=["地方戏曲", "越剧", "昆曲", "昆剧", "黄梅戏", "豫剧", "川剧", "粤剧", "评剧", "秦腔", "地方戏"],
   summary="京剧之外各地方剧种的总类——越剧、昆曲、黄梅戏、豫剧、川剧、秦腔等各有特色；优先选本地有院团、有少儿传承班的剧种。",
   abilities={"expression": 2, "aesthetic": 2, "physical": 1, "focus": 1},
   traits=dict(indoor="indoor", group="both", tempo="active", cost="mid")),
 "皮影/木偶戏体验": dict(
   id="drama-puppet", aliases=["皮影戏", "木偶戏"],
   summary="以体验与欣赏为主的地方特色艺术形式。",
   abilities={"aesthetic": 1, "hands_on": 1, "creativity": 1},
   traits=dict(indoor="both", group="both", tempo="calm", cost="low"),
   family_ok=True),
 "双语戏剧": dict(
   id="drama-bilingual", aliases=["英文戏剧"],
   summary="英语底子+表演兴趣的结合体，入小学后再议。",
   abilities={"expression": 2, "social": 1},
   traits=dict(indoor="indoor", group="team", tempo="active", cost="mid"),
   caution="学龄前阶段同英语口径：学科类（含外语）培训违规。"),
 "第二外语": dict(
   id="drama-l2", aliases=["日语", "法语", "第二外语"],
   summary="建议英语站稳后再考虑的其他语种。",
   abilities={"expression": 2, "logic": 1},
   traits=dict(indoor="indoor", group="both", tempo="calm", cost="mid"),
   caution="学龄前外语类学科培训同属双减禁止范围。"),
 "配音/播音主持专业向": dict(
   id="drama-dubbing", aliases=["配音", "播音主持"],
   summary="专业向的语言训练，童声变声前不搞。",
   abilities={"expression": 2, "focus": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="mid")),
 # ---- 十、美术/手工 ----
 "创意美术": dict(
   id="art-creative", aliases=["美术启蒙", "儿童画"],
   summary="以自由表达为主的'过程艺术'课堂，是 3-7 岁美术学习的正确形式。",
   abilities={"creativity": 2, "aesthetic": 2, "hands_on": 1, "focus": 1},
   traits=dict(indoor="indoor", group="both", tempo="calm", cost="mid"),
   caution="选'过程艺术'课堂（自由表达为主、没有范画临摹）——罗恩菲德理论：4-7 岁前图式期应鼓励自由表达，范画临摹与技法前置有害。"),
 "陶艺（亲子）": dict(
   id="art-pottery", aliases=["陶艺", "拉坯"],
   summary="练专注的'慢活动'，与运动形成互补。",
   abilities={"hands_on": 2, "focus": 2, "creativity": 1},
   traits=dict(indoor="indoor", group="both", tempo="calm", cost="mid")),
 "少儿木工": dict(
   id="art-woodcraft", aliases=["木工课"],
   summary="动手+空间感+安全意识的综合手工课。",
   abilities={"hands_on": 2, "focus": 1, "creativity": 1, "logic": 1},
   traits=dict(indoor="indoor", group="both", tempo="active", cost="mid"),
   caution="低龄以亲子形式进行，注意工具安全规范。"),
 "超轻黏土/软陶": dict(
   id="art-clay", aliases=["黏土", "软陶", "少儿雕塑"],
   summary="在家就能做的精细动作练习。",
   abilities={"hands_on": 2, "creativity": 2, "focus": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="low"),
   family_ok=True),
 "折纸/剪纸": dict(
   id="art-paper", aliases=["折纸", "剪纸"],
   summary="免费的手部精细课（剪纸用安全剪刀）。",
   abilities={"hands_on": 2, "focus": 1, "creativity": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="low"),
   family_ok=True),
 "国画": dict(
   id="art-chinese-painting", aliases=["水墨画"],
   summary="握笔力量要求较高的传统绘画形式。",
   abilities={"aesthetic": 2, "hands_on": 1, "focus": 2},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="mid"),
   note="6 岁后学更稳。"),
 "书法/硬笔": dict(
   id="art-calligraphy", aliases=["书法", "硬笔书法", "练字", "软笔书法", "毛笔字"],
   summary="小学阶段的刚需技能，但不早学（手部骨骼与握笔精细度）。",
   abilities={"focus": 2, "aesthetic": 1, "hands_on": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="low"),
   note="一般 6 岁后（入学前后）开始。"),
 "水彩/油画": dict(
   id="art-painting", aliases=["水彩", "油画"],
   summary="创意美术的进阶方向。",
   abilities={"aesthetic": 2, "creativity": 2, "hands_on": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="mid")),
 "沙画": dict(
   id="art-sand", aliases=[],
   summary="娱乐体验向的视觉艺术形式。",
   abilities={"creativity": 1, "aesthetic": 1, "hands_on": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="low"),
   family_ok=True),
 "动漫画": dict(
   id="art-manga", aliases=["动漫绘画", "漫画"],
   summary="画自己喜欢的东西是最好的动力，但技法要等。",
   abilities={"creativity": 2, "aesthetic": 1, "hands_on": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="mid")),
 "摄影": dict(
   id="art-photography", aliases=["少儿摄影"],
   summary="观察力训练，旧手机就能入门。",
   abilities={"creativity": 2, "aesthetic": 2, "focus": 1, "hands_on": 1},
   traits=dict(indoor="both", group="solo", tempo="calm", cost="low")),
 "素描": dict(
   id="art-sketch", aliases=["素描基础"],
   summary="写实技法训练，对应罗恩菲德'写实萌芽期（9-11 岁）'，9 岁前不学。",
   abilities={"aesthetic": 1, "focus": 2, "hands_on": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="mid"),
   policy="caution",
   age_start=9,
   caution="罗恩菲德绘画发展阶段：涂鸦期2-4岁→前图式期4-7岁→图式期7-9岁→写实萌芽期9-11岁；写实/素描训练对应 9 岁后，8 岁前红线维持，技法前置会扼杀想象力。"),
 "插画/平面设计": dict(
   id="art-illustration", aliases=["插画", "平面设计"],
   summary="美术兴趣的数字化延伸。",
   abilities={"creativity": 2, "aesthetic": 2, "hands_on": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="mid")),
 # ---- 十一、自然/营地/户外 ----
 "自然教育课（周末森林课）": dict(
   id="nature-forest", aliases=["森林课", "自然教育", "周末森林课"],
   summary="幼儿阶段被严重低估的项目：感官+好奇心的总开关，顺带完成每天户外 2 小时目标。",
   abilities={"hands_on": 1, "logic": 1, "focus": 1, "physical": 1, "creativity": 1},
   traits=dict(indoor="outdoor", group="team", tempo="active", cost="mid"),
   note="《3-6岁儿童学习与发展指南》科学领域：'经常带幼儿接触大自然，激发其好奇心与探究欲望'。"),
 "观鸟": dict(
   id="nature-birdwatching", aliases=["鸟类观察"],
   summary="一本图鉴+望远镜就入门的观察爱好，看图鉴找鸟是最早的'查表检索'训练。",
   abilities={"focus": 2, "logic": 1, "hands_on": 1},
   traits=dict(indoor="outdoor", group="both", tempo="calm", cost="low"),
   family_ok=True),
 "昆虫观察/饲养": dict(
   id="nature-insects", aliases=["昆虫课", "养虫"],
   summary="家门口即可开展，观察记录就是最早的'科学写作'。",
   abilities={"logic": 1, "focus": 1, "hands_on": 1},
   traits=dict(indoor="both", group="solo", tempo="calm", cost="low"),
   family_ok=True),
 "博物馆研学": dict(
   id="nature-museum", aliases=["博物馆课", "研学"],
   summary="养成'馆虫'比报三个班都值，城市博物馆资源是公共教育富矿。",
   abilities={"logic": 1, "aesthetic": 1, "focus": 1},
   traits=dict(indoor="indoor", group="both", tempo="calm", cost="low"),
   family_ok=True),
 "种植/园艺": dict(
   id="nature-gardening", aliases=["种植课", "园艺", "阳台种菜"],
   summary="阳台种菜+每天记录生长，免费的自然科学+数学观察课。",
   abilities={"hands_on": 2, "focus": 1, "logic": 1},
   traits=dict(indoor="both", group="solo", tempo="calm", cost="low"),
   family_ok=True),
 "家庭桌游": dict(
   id="nature-board-games", aliases=["桌游", "board game"],
   summary="规则意识+数数+抗挫的综合游戏，屏幕时间的最优替代品，几十块一套。",
   abilities={"logic": 2, "social": 2, "focus": 1},
   traits=dict(indoor="indoor", group="team", tempo="calm", cost="low"),
   family_ok=True),
 "骑行（自行车）": dict(
   id="nature-cycling", aliases=["自行车", "骑车", "公路自行车", "场地自行车", "山地自行车"],
   summary="亚运/奥运大项（公路、场地、山地、BMX 等分项）；对儿童来说先是平衡车/辅助轮→两轮的户外放电核心项目，专项训练 8 岁后再谈。",
   abilities={"physical": 2, "focus": 1, "resilience": 1},
   traits=dict(indoor="outdoor", group="solo", tempo="active", cost="mid"),
   caution="《道路交通安全法实施条例》第72条：骑自行车上路须年满 12 周岁、驾驶电动自行车须年满 16 周岁——未满法定年龄只在公园/绿道/封闭场地骑行；任何年龄都不参加成人公路骑行团，头盔必戴。",
   note="日间户外活动对近视防控有明确价值（卫健委口径：每天 2 小时以上最有效）。2025 年河北一名 11 岁男孩随成年骑行团在公路骑行时摔倒遭对向车辆碾压身亡，此类'亲子拉练式骑行'必须远离。"),
 "露营/徒步/登山": dict(
   id="nature-hiking", aliases=["露营", "徒步", "登山"],
   summary="家庭活动不是课程，但价值极高；3 岁起即可参与短途户外。",
   abilities={"physical": 1, "resilience": 1, "social": 1, "hands_on": 1},
   traits=dict(indoor="outdoor", group="both", tempo="active", cost="mid"),
   age_start=3,
   family_ok=True),
 "亲子钓鱼": dict(
   id="nature-fishing", aliases=["钓鱼"],
   summary="练等待与专注的慢活动。",
   abilities={"focus": 2, "resilience": 1},
   traits=dict(indoor="outdoor", group="both", tempo="calm", cost="low"),
   family_ok=True),
 "童军/营地教育/夏令营": dict(
   id="nature-camp", aliases=["夏令营", "营地教育", "童军"],
   summary="独立性与团队生活的系统训练，先亲子营、7 岁后再过夜单飞。",
   abilities={"resilience": 2, "social": 2, "hands_on": 1, "physical": 1},
   traits=dict(indoor="outdoor", group="team", tempo="active", cost="high")),
 "溯溪/漂流": dict(
   id="nature-rafting", aliases=["溯溪", "漂流"],
   summary="有明确安全年龄门槛的水上户外活动。",
   abilities={"physical": 1, "resilience": 2, "focus": 1},
   traits=dict(indoor="outdoor", group="team", tempo="active", cost="mid"),
   caution="遵守营地的安全年龄门槛（一般 8 岁+）。"),
 "马术": dict(
   id="nature-equestrian", aliases=["骑马", "马术课"],
   age_start=6,
   summary="人畜协作的贵族气质运动，费用与资源门槛都高。",
   abilities={"physical": 2, "resilience": 1, "social": 1},
   traits=dict(indoor="outdoor", group="solo", tempo="active", cost="high"),
   status="active",
   note="高成本项目：课时费与装备费用高，网页端按成本筛选即可，无需特殊处理。"),
 # ---- 十二、生活技能 ----
 "亲子烘焙/烹饪": dict(
   id="life-baking", aliases=["烘焙课", "烹饪课", "儿童厨房"],
   summary="称量搅拌全是精细动作+应用数学，在家就能搞。",
   abilities={"hands_on": 2, "logic": 1, "focus": 1},
   traits=dict(indoor="indoor", group="both", tempo="calm", cost="low"),
   family_ok=True),
 "收纳整理": dict(
   id="life-organizing", aliases=["整理课"],
   summary="家教比报班有效的秩序感训练。",
   abilities={"logic": 1, "hands_on": 1, "focus": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="low"),
   family_ok=True),
 "茶道/花艺": dict(
   id="life-tea", aliases=["茶道", "花艺"],
   summary="仪式感项目，大点再学。",
   abilities={"focus": 1, "aesthetic": 1, "social": 1},
   traits=dict(indoor="indoor", group="both", tempo="calm", cost="low")),
 "少年急救课": dict(
   id="life-first-aid", aliases=["急救课"],
   summary="实用技能，红十字会/营地常有亲子班。",
   abilities={"hands_on": 2, "social": 1, "focus": 1},
   traits=dict(indoor="indoor", group="both", tempo="calm", cost="low")),
 "财商进阶（零花钱制度）": dict(
   id="life-allowance", aliases=["零花钱制度"],
   summary="制度设计好就够，不用花钱上课。",
   abilities={"logic": 1, "focus": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="low"),
   family_ok=True),
 "感统训练（干预型）": dict(
   id="life-sensory", aliases=["感统训练", "感觉统合"],
   summary="发育正常的孩子做感统训练往往没有效果，机构宣传有贩卖焦虑之嫌。",
   abilities={},
   traits=dict(indoor="indoor", group="solo", tempo="active", cost="high"),
   policy="discouraged",
   caution="人民日报（引 AAP 发育行为儿科学教科书）：'给发育正常的孩子进行感统训练往往没有效果'；若孩子确有发育表现，先去医院儿科排查（孤独症/多动症等根源），按医嘱行事，不进商业机构。"),
 # ---- 亚运大项对照补充（2026-10-31，以 2026 爱知名古屋亚运会 43 个大项为体育类完备性基准）----
 "柔道": dict(
   id="combat-judo", aliases=["少儿柔道"],
   summary="亚运/奥运大项：以投技与地面寝技为核心的对抗项目，最讲究礼节与'受身'（安全倒地）教学。",
   abilities={"physical": 2, "resilience": 2, "focus": 1, "social": 1},
   traits=dict(indoor="indoor", group="both", tempo="active", cost="mid"),
   age_start=5, age_window="行业惯例 5-6 岁可上少儿柔道课",
   caution="选强调受身（安全倒地）训练、实战对抗环节低龄不硬性要求的道场。",
   note="亚运大项对照新增。"),
 "克拉术": dict(
   id="combat-kurash", aliases=["库拉什", "Kurash"],
   summary="中亚传统抓把摔对抗项目（亚运正式大项），规则近似柔道但无地面技，直摔定胜负。",
   abilities={"physical": 2, "resilience": 1, "focus": 1},
   traits=dict(indoor="indoor", group="both", tempo="active", cost="mid"),
   age_start=8, age_window="无国内少儿体系，了解为主",
   note="亚运大项对照新增；国内少儿培训体系极少，同类兴趣可先从柔道/摔跤起步。"),
 "综合格斗（MMA）": dict(
   id="combat-mma", aliases=["MMA", "混合武术"],
   summary="站立打击+摔法+地面缠斗的混合对抗项目，2026 名古屋亚运会新增大项。",
   abilities={"physical": 2, "resilience": 2},
   traits=dict(indoor="indoor", group="both", tempo="active", cost="mid"),
   age_start=12, age_window="少儿阶段不建议，12 岁后再议",
   policy="caution",
   refs=["r19"],
   caution="含头部击打成分——AAP 对'以击打头部为得分手段'的儿童对抗运动的反对口径同样适用；少儿阶段建议拆选柔道、巴西柔术、摔跤等单项，避免过早综合对抗。",
   note="亚运大项对照新增。"),
 "卡巴迪": dict(
   id="ball-kabaddi", aliases=["Kabaddi"],
   summary="南亚团队追逐类运动（亚运正式大项）：进攻方突袭触防并折返、防守方围堵，跑动躲闪价值高。",
   abilities={"physical": 2, "social": 2, "resilience": 1},
   traits=dict(indoor="outdoor", group="team", tempo="active", cost="low"),
   age_start=8, age_window="无国内青训体系，了解为主",
   note="亚运大项对照新增；国内培训资源极少，其跑动躲闪价值体能课与追逐游戏可承接。"),
 "藤球": dict(
   id="ball-sepak-takraw", aliases=["Sepak Takraw"],
   summary="用脚、膝、头完成传接扣杀的东南亚特色网球类运动（亚运正式大项），俗称'脚踢的排球'。",
   abilities={"physical": 2, "focus": 1, "resilience": 1},
   traits=dict(indoor="both", group="team", tempo="active", cost="low"),
   age_start=8, age_window="资源集中在中缅边境地区与高校，了解为主",
   note="亚运大项对照新增；控球柔韧价值可由足球/排球承接。"),
 "板式网球": dict(
   id="ball-padel", aliases=["帕德尔球", "Padel", "板网球"],
   summary="围墙玻璃板+短拍的网球变体（2026 名古屋亚运会新增大项），上手快、回合多、社交性强，一线城市场馆正在兴起。",
   abilities={"physical": 2, "focus": 1, "social": 1},
   traits=dict(indoor="both", group="both", tempo="active", cost="mid"),
   age_start=5, age_window="行业惯例 5-6 岁可体验",
   note="亚运大项对照新增；网球基础可直接迁移。"),
 "举重（力量训练）": dict(
   id="fitness-weightlifting", aliases=["力量训练", "少儿力量", "抓举", "挺举"],
   summary="亚运/奥运大项；对儿童而言指科学力量训练（自重、动作模式），竞技举重是青春期后的进阶方向。",
   abilities={"physical": 2, "focus": 1},
   traits=dict(indoor="indoor", group="solo", tempo="active", cost="low"),
   age_start=12, age_window="12 岁前以自重与动作模式为主",
   caution="儿童青少年不做最大重量冲刺：儿科运动医学共识口径为以自重与轻负荷练动作模式，进入青春期后再考虑杠铃系统训练；体能课中的力量游戏是低龄正确形式。",
   note="亚运大项对照新增。"),
 "现代五项": dict(
   id="fitness-pentathlon", aliases=["五项全能"],
   summary="击剑+游泳+马术+跑步+射击联项的综合性项目（亚运/奥运大项），对单项底子要求全面。",
   abilities={"physical": 2, "focus": 2, "resilience": 1},
   traits=dict(indoor="both", group="solo", tempo="active", cost="high"),
   age_start=10, age_window="资源极少；先以击剑、游泳单项打基础",
   note="亚运大项对照新增；普通家庭了解为主。"),
 "龙舟": dict(
   id="water-dragon-boat", aliases=["划龙舟", "龙舟队"],
   summary="中国传统团队水上项目（亚运正式大项）：练爆发划桨、节奏同频与集体荣誉感。",
   abilities={"physical": 2, "social": 2, "focus": 1},
   traits=dict(indoor="outdoor", group="team", tempo="active", cost="mid"),
   age_start=6, age_window="以营地/俱乐部体验与亲子形式为主",
   caution="水上活动：全程穿救生衣、确认有救生员/安全员在场。",
   note="亚运大项对照新增。"),
 "冲浪": dict(
   id="water-surfing", aliases=["冲浪板", "滑水"],
   summary="平衡与读浪的水上运动（2026 名古屋亚运会新增大项），滨海城市营地体验形式普及中。",
   abilities={"physical": 2, "resilience": 2, "focus": 1},
   traits=dict(indoor="outdoor", group="solo", tempo="active", cost="high"),
   age_start=8, age_window="行业惯例 8 岁+，先营地体验",
   caution="初学选浅水教学区、教练小班看护、脚绳救生装备齐全；不会游泳不冲浪。",
   note="亚运大项对照新增。"),
 "电子竞技": dict(
   id="mind-esports", aliases=["电竞", "游戏竞技", "电竞班"],
   summary="以竞技游戏为载体的正式体育项目（亚运大项）；作为儿童兴趣的核心命题是屏幕管理与自控，职业通道极窄。",
   abilities={"logic": 1, "focus": 1, "resilience": 1},
   traits=dict(indoor="indoor", group="both", tempo="calm", cost="low"),
   age_start=12, age_window="学龄期以家庭屏幕约定为前提，12 岁前不建议",
   family_ok=True,
   refs=["r10"],
   caution="学龄前没有电子屏的必要（教育部口径幼儿连续用电子产品≤15分钟）；市面'电竞班'营销大于实质，游戏本身即可自学——为游戏付费报班是典型的为焦虑买单。",
   note="亚运大项对照新增；收录目的是给搜索家长一个客观口径，而非推荐。"),
 # ---- 艺术类完备性补充（2026-10-31：音乐按键盘/弦乐/民乐/管乐/打击乐/电声六家族，美术按绘画/立体/工艺/数字四门类盘点）----
 "电子琴": dict(
   id="music-keyboard", aliases=["电子键盘", "双排键"],
   summary="键盘家族的低门槛入口：音准自带、见效快，是乐理启蒙与识谱训练的常见载体。",
   abilities={"aesthetic": 2, "focus": 1, "hands_on": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="low"),
   age_start=5, age_window="行业惯例 5 岁起，与钢琴启蒙同窗",
   note="艺术类完备性补充；后续转钢琴衔接顺滑，预算敏感家庭的主流起步。"),
 "手风琴": dict(
   id="music-accordion", aliases=["手风琴课"],
   summary="风箱气息+左手贝斯系统+右手键盘三线并开的全能乐器，考级与艺术团体系成熟。",
   abilities={"aesthetic": 2, "hands_on": 1, "physical": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="mid"),
   age_start=6, age_window="行业惯例 6-7 岁（风箱力度）",
   note="艺术类完备性补充；乐器自重不小，选儿童尺寸琴。"),
 "扬琴": dict(
   id="music-yangqin", aliases=["扬琴课"],
   summary="民乐团击弦乐部核心：双槌独立击弦，等于高配版手眼协调训练。",
   abilities={"aesthetic": 2, "hands_on": 2, "focus": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="mid"),
   age_start=6.5, age_window="行业惯例 6-7 岁",
   note="艺术类完备性补充；民族管弦乐团刚需声部，考级体系成熟。"),
 "中阮/柳琴": dict(
   id="music-ruan", aliases=["阮", "柳琴", "中阮", "大阮"],
   summary="弹拨乐中音乐器（亚运常设民乐配置）：音色温润，柳琴为高音小尺寸先行版。",
   abilities={"aesthetic": 2, "hands_on": 1, "focus": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="mid"),
   age_start=7, age_window="行业惯例 7 岁+（柳琴可早半年）",
   note="艺术类完备性补充；民乐团稀缺声部，走团体路线有优势。"),
 "唢呐": dict(
   id="music-suona", aliases=["唢呐班"],
   summary="个性最强烈的传统簧管乐器：肺活量与换牙要求高，音量极大。",
   abilities={"aesthetic": 2, "physical": 1, "resilience": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="low"),
   age_start=8, age_window="行业惯例 8 岁+（换牙后）",
   caution="家庭需接受大音量练习；民乐极小众方向，先确认本地有老师。",
   note="艺术类完备性补充。"),
 "笙": dict(
   id="music-sheng", aliases=["笙课"],
   summary="唯一能同时吹奏和声的传统乐器，民乐团稀缺声部，气息训练扎实。",
   abilities={"aesthetic": 2, "hands_on": 1, "physical": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="mid"),
   age_start=8, age_window="行业惯例 8 岁+（肺活量）",
   note="艺术类完备性补充；与唢呐同属极小众方向。"),
 "古琴": dict(
   id="music-guqin", aliases=["七弦琴", "古琴课"],
   summary="文人乐器：减字谱、慢节奏、重文化深度，适合坐得住、喜欢传统文化的孩子。",
   abilities={"aesthetic": 2, "focus": 2, "resilience": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="mid"),
   age_start=9, age_window="行业惯例 9-10 岁起更普遍",
   note="艺术类完备性补充；与筝不同——不求热闹，求静与深。"),
 "竖琴": dict(
   id="music-harp", aliases=["竖琴课"],
   summary="音色梦幻的拨弦乐器：少年宫/院团资源导向，器材昂贵。",
   abilities={"aesthetic": 2, "hands_on": 1, "focus": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="high"),
   age_start=6, age_window="行业惯例 6-8 岁，先确认本地资源",
   note="艺术类完备性补充；中央院考级有体系，一线城市为主。"),
 "低音提琴": dict(
   id="music-double-bass", aliases=["贝斯提琴", "低音贝斯"],
   summary="管弦乐团低音声部：琴体大、儿童尺寸琴少，走乐团路线时再选。",
   abilities={"aesthetic": 2, "hands_on": 1, "social": 1},
   traits=dict(indoor="indoor", group="both", tempo="calm", cost="high"),
   age_start=8, age_window="行业惯例 8 岁+，以乐团招募为导向",
   note="艺术类完备性补充；稀缺声部，升学乐团方向有通道价值。"),
 "萨克斯": dict(
   id="music-sax", aliases=["Sax", "萨克斯风"],
   summary="爵士与流行通吃的单簧片管乐，演出机会多，是管乐里'舞台感'最强的一支。",
   abilities={"aesthetic": 2, "hands_on": 1, "physical": 1},
   traits=dict(indoor="indoor", group="both", tempo="calm", cost="mid"),
   age_start=8, age_window="行业共识：换牙后（约 8-9 岁）起步",
   refs=["r18"],
   caution="乐器自重不小、气息要求高，低龄不合适；建议先口风琴/竖笛过渡。",
   note="艺术类完备性补充。"),
 "课堂乐器（口风琴/口琴/竖笛）": dict(
   id="music-classroom", aliases=["口风琴", "口琴", "竖笛", "笛子课"],
   summary="学校音乐课堂的标配乐器：识谱与气息启蒙，在家即可开展。",
   abilities={"aesthetic": 2, "hands_on": 1, "focus": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="low"),
   age_start=6, age_window="与学校音乐课同步（约 6 岁+）",
   family_ok=True,
   note="艺术类完备性补充；不是长期赛道，是音乐素养的过渡台阶。"),
 "打击乐（马林巴/小军鼓）": dict(
   id="music-mallet", aliases=["马林巴", "小军鼓", "民族打击乐", "排鼓"],
   summary="专业打击乐路线：从键盘类打击乐（马林巴）起步，乐团刚需声部。",
   abilities={"aesthetic": 2, "hands_on": 2, "focus": 2},
   traits=dict(indoor="indoor", group="both", tempo="active", cost="mid"),
   age_start=6, age_window="行业惯例 6 岁+（爵士鼓/非洲鼓之外的古典方向）",
   note="艺术类完备性补充；与爵士鼓条目互为补充，走乐团方向选这里。"),
 "少儿乐队（电吉他/贝斯/主唱）": dict(
   id="music-band", aliases=["电吉他", "贝斯", "乐队课", "摇滚学校", "电声乐队"],
   summary="电声乐队集体课：分声部排练、上舞台，社交与舞台感的成长极快。",
   abilities={"social": 2, "aesthetic": 2, "resilience": 1},
   traits=dict(indoor="indoor", group="team", tempo="active", cost="mid"),
   age_start=8, age_window="行业惯例 8 岁+（先有单项乐器基础更佳）",
   note="艺术类完备性补充；全国连锁品牌化运营，试听时看舞台机会是否真实。"),
 "乐理/视唱练耳": dict(
   id="music-theory", aliases=["视唱练耳", "乐理考级", "乐理课"],
   summary="器乐学习的配套必修：识谱、音准、节奏的系统训练，考级四级以上普遍要求。",
   abilities={"logic": 2, "focus": 1, "aesthetic": 1},
   traits=dict(indoor="indoor", group="both", tempo="calm", cost="low"),
   age_start=6, age_window="随器乐学习配套开始（约 6 岁+）",
   family_ok=True,
   note="艺术类完备性补充；不单独立项报班也行，好器乐老师会顺带教。"),
 "版画": dict(
   id="art-print", aliases=["木刻版画", "拓印"],
   summary="'画—刻—印'三段式的间接艺术：过程感极强，转印瞬间的惊喜是孩子最爱的部分。",
   abilities={"hands_on": 2, "creativity": 2, "focus": 1},
   traits=dict(indoor="indoor", group="both", tempo="calm", cost="mid"),
   age_start=6, age_window="6 岁+纸版/吹塑版起步，木刻 10 岁+",
   caution="刻刀类版画 10 岁后再上，低龄用吹塑纸与安全刻具。",
   note="艺术类完备性补充。"),
 "篆刻": dict(
   id="art-seal", aliases=["印章", "刻印"],
   summary="方寸之间的书法+刀法艺术，与书法同修最佳，文化含量高。",
   abilities={"focus": 2, "hands_on": 2, "aesthetic": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="low"),
   age_start=10, age_window="10 岁+（握刀力度与安全）",
   caution="刻刀安全：选软石（寿山/青田练习石）与安全握刀姿势教学。",
   note="艺术类完备性补充。"),
 "传统手工（扎染/面塑/灯笼/风筝）": dict(
   id="art-craft", aliases=["扎染", "面塑", "捏面人", "风筝制作", "非遗手工", "扭扭棒", "鲁班锁"],
   summary="非遗工坊式手工体验：染、塑、扎、糊各有门道，周末体验课遍地，在家也能玩。",
   abilities={"hands_on": 2, "creativity": 1, "focus": 1},
   traits=dict(indoor="both", group="both", tempo="calm", cost="low"),
   age_start=4, age_window="4 岁+亲子，7 岁+独立",
   family_ok=True,
   note="艺术类完备性补充；皮影/木偶条目覆盖观演体验，本条覆盖动手制作。"),
 "布艺/缝纫/编织": dict(
   id="art-sewing", aliases=["缝纫", "编织", "毛线", "服装设计", "少儿服装设计"],
   summary="从穿珠缝扣到做小包、改小裙子：精细动作+设计思维的实用艺术。",
   abilities={"hands_on": 2, "focus": 2, "creativity": 1},
   traits=dict(indoor="indoor", group="both", tempo="calm", cost="low"),
   age_start=6, age_window="6 岁+钝针起步，缝纫机 10 岁+",
   caution="针具安全：低龄用塑料钝针、家长陪同；缝纫机环节 10 岁后。",
   note="艺术类完备性补充；服装设计方向机构较少，先从布艺基础玩起。"),
 "数字绘画/板绘": dict(
   id="art-digital", aliases=["板绘", "Procreate", "数字美术"],
   summary="用平板/数位板作画：图层、撤销、色彩无限，创意实现的现代画笔。",
   abilities={"creativity": 2, "aesthetic": 2, "hands_on": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="low"),
   age_start=9, age_window="9 岁+（已过创意美术阶段、有纸面基础）",
   family_ok=True,
   caution="屏幕时间与护眼约定优先；先纸面后板面，别让'设备'替代'观察'。",
   note="艺术类完备性补充；与插画/平面设计条目衔接。"),
 "少儿影像（短视频/定格动画）": dict(
   id="art-video", aliases=["定格动画", "Vlog", "短视频创作"],
   summary="用镜头讲故事：分镜、拍摄、剪辑，数字时代最实用的表达载体，定格动画尤其适合孩子。",
   abilities={"creativity": 2, "hands_on": 2, "expression": 1},
   traits=dict(indoor="both", group="both", tempo="calm", cost="low"),
   age_start=8, age_window="8 岁+，定格动画/家庭Vlog起步",
   family_ok=True,
   refs=["r10"],
   caution="屏幕时间约定优先；不追求流量与曝光——孩子内容的发布涉及肖像与隐私，家长必须把关，警惕'儿童网红'方向的机构话术。",
   note="艺术类完备性补充。"),
 "音乐剧": dict(
   id="drama-musical", aliases=["少儿音乐剧"],
   summary="唱、跳、演一体的综合舞台艺术：表达欲和舞台感的'终极载体'，一线城市发展迅猛。",
   abilities={"expression": 2, "aesthetic": 2, "social": 1, "resilience": 1},
   traits=dict(indoor="indoor", group="team", tempo="active", cost="mid"),
   age_start=5, age_window="行业惯例 5-6 岁+",
   note="艺术类完备性补充；对声乐、舞蹈、戏剧三个条目是'合体升级'，先有单项兴趣再入更稳。"),
 "魔术": dict(
   id="drama-magic", aliases=["近景魔术", "魔术课"],
   summary="手技+台词+心理素质的综合表演：成就感即时，是慢热孩子练胆量的秘密武器。",
   abilities={"hands_on": 2, "focus": 2, "expression": 1, "resilience": 1},
   traits=dict(indoor="indoor", group="both", tempo="calm", cost="low"),
   age_start=6, age_window="行业惯例 6-7 岁+",
   family_ok=True,
   note="艺术类完备性补充；好课程教'表演'而不只教'手法'。"),
 "少儿模特（形体礼仪）": dict(
   id="drama-model", aliases=["童模", "T台", "形体礼仪", "童星班", "影视小演员"],
   summary="T台走秀与形体训练类课程；形体价值有限且可由舞蹈课替代——收录主要是给搜索家长一个风险提示。",
   abilities={"physical": 1, "expression": 1, "social": 1},
   traits=dict(indoor="indoor", group="both", tempo="calm", cost="mid"),
   age_start=4, age_window="行业招生多在 4-10 岁",
   policy="caution",
   caution="行业乱象高发：警惕'签约出道''包装童星''交钱上秀'的收费套路与拍照陷阱，公安机关多次提示'童星招募'类骗局；确有表演兴趣，先从儿童戏剧/口才起步，形体需求交给舞蹈课。",
   note="艺术类完备性补充；与少儿影像条目的隐私提示互为呼应。"),
 # ---- 科技类完备性补充（2026-10-31：按编程AI/机器人硬件/模型/科学观察/思维五条线盘点）----
 "人工智能/AI启蒙": dict(
   id="mind-ai", aliases=["AI课", "AI启蒙", "人工智能课"],
   summary="认识AI、用AI做小项目（图像识别、训练小模型等）的课程；官方已部署中小学AI教育，选课时认'思维培养'不认'工具打卡'。",
   abilities={"logic": 2, "focus": 1, "creativity": 1},
   traits=dict(indoor="indoor", group="both", tempo="calm", cost="mid"),
   age_start=8, age_window="行业惯例 8 岁+（有Scratch基础更佳）",
   note="科技类完备性补充；别被'AI焦虑营销'带跑——这个年龄段的AI教育核心是计算思维启蒙，不是学某个软件。"),
 "创客/开源硬件": dict(
   id="mind-maker", aliases=["Arduino", "micro:bit", "单片机", "创客课"],
   summary="用开源硬件做真实的小发明：传感器、灯带、小车……编程离开屏幕、走进物理世界。",
   abilities={"hands_on": 2, "logic": 2, "creativity": 1},
   traits=dict(indoor="indoor", group="both", tempo="calm", cost="mid"),
   age_start=9, age_window="行业惯例 9-10 岁（micro:bit 可早至 8 岁）",
   note="科技类完备性补充；机器人建构课的自然下一步，对接青少年科技创新竞赛体系。"),
 "电子电路/电子积木": dict(
   id="mind-circuit", aliases=["电子积木", "电路实验", "Snap Circuits"],
   summary="磁吸/卡扣式电子积木拼电路：让灯亮、风扇转，安全的'第一次电学'，在家就能玩。",
   abilities={"hands_on": 2, "logic": 1, "focus": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="low"),
   age_start=6, age_window="6 岁+亲子起步",
   family_ok=True,
   note="科技类完备性补充；创客/机器人的低龄前置。"),
 "3D建模/3D打印": dict(
   id="mind-3dprint", aliases=["3D打印", "三维建模"],
   summary="把自己设计的模型变成实物：空间思维+设计思维的现代制造入门。",
   abilities={"hands_on": 2, "creativity": 2, "logic": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="mid"),
   age_start=8, age_window="行业惯例 8 岁+",
   note="科技类完备性补充；与乐高/车模/创客条目互为补充。"),
 "显微观察": dict(
   id="mind-microscope", aliases=["显微镜", "微观世界"],
   summary="一台儿童显微镜打开微观世界：洋葱表皮、水里的微生物，观察记录就是最早的科学习惯。",
   abilities={"focus": 2, "logic": 1, "hands_on": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="low"),
   age_start=6, age_window="6 岁+立体显微镜起步，复式显微镜 8 岁+",
   family_ok=True,
   note="科技类完备性补充；与天文观测条目构成'远近两个世界'。"),
 "航天启蒙/火箭模型": dict(
   id="mind-space", aliases=["航天", "火箭模型", "水火箭", "太空课"],
   summary="中国航天热带来的科普赛道：认识太阳系与火箭原理，水火箭/模型火箭动手发射。",
   abilities={"logic": 1, "focus": 1, "hands_on": 1, "creativity": 1},
   traits=dict(indoor="both", group="both", tempo="calm", cost="low"),
   age_start=6, age_window="6 岁+科普起步，模型火箭 8 岁+",
   family_ok=True,
   caution="模型火箭/水火箭活动认准营地与社团的规范场地，不在小区乱发射。",
   note="科技类完备性补充；与航模条目区分——航模是飞行器，航天是太空方向。"),
 "无线电测向/业余无线电": dict(
   id="mind-radio", aliases=["无线电测向", "抓狐狸", "HAM", "业余无线电"],
   summary="'边跑边收报'的科技体育：手持测向机找隐蔽电台，技术+定向跑动合一，小众但体系成熟。",
   abilities={"focus": 2, "logic": 1, "hands_on": 1, "physical": 1},
   traits=dict(indoor="outdoor", group="both", tempo="active", cost="low"),
   age_start=8, age_window="行业惯例 8 岁+，少年宫/科技馆渠道为主",
   note="科技类完备性补充；与定向越野是近亲，资源稀缺但真实存在。"),
 "数学思维/奥数": dict(
   id="mind-math", aliases=["奥数", "数学思维", "数学培优"],
   summary="小学数学思维拓展与竞赛数学（奥数）：对真有兴趣的孩子是智力体操，被裹挟报班则是灾难。",
   abilities={"logic": 2, "focus": 1},
   traits=dict(indoor="indoor", group="both", tempo="calm", cost="mid"),
   age_start=7, age_window="低年级以趣味数学思维为主，竞赛方向 3-4 年级后再议",
   refs=["r4"],
   caution="属学科类培训，受'双减'严格监管：必须选择持证合规机构；学龄前一切数学思维班均属违规（见幼小衔接条目）。判断标准不是'别人都学'，而是孩子做难题时眼里有没有光。",
   note="科技类完备性补充；收录以给准确政策口径为主。"),
 # ---- 英语路线分层（2026-10-31：国家不鼓励但家长搜索量大，如实分层收录、政策状态讲清楚）----
 "英语绘本/分级阅读": dict(
   id="drama-english-reading", aliases=["英语绘本", "分级阅读", "RAZ", "牛津树", "英文亲子阅读"],
   summary="英语的'正规家庭路线'：从亲子共读英文绘本到分级读物爬坡，重阅读兴趣与听力词汇积累，不卷考级。",
   abilities={"expression": 2, "logic": 1, "focus": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="low"),
   age_start=3, age_window="3 岁+亲子共读，识字后自读分级读物",
   family_ok=True,
   caution="家庭阅读完全没问题；但机构化'绘本英语课'若实质是英语教学，学龄前同样属学科类违规办学，别换包装就放松。",
   note="英语路线分层新增；与英语启蒙（磨耳朵）、剑桥考级条目构成完整路线图。"),
 "剑桥英语考级（YLE/KET/PET）": dict(
   id="drama-english-cambridge", aliases=["剑桥英语", "剑桥少儿英语", "KET", "PET", "YLE", "剑少"],
   summary="剑桥大学英语考评部的国际英语证书体系：剑桥少儿英语（YLE）约 6-12 岁，KET/PET 多在 9-12 岁；考试本身合法存在。",
   abilities={"expression": 1, "logic": 1},
   traits=dict(indoor="indoor", group="both", tempo="calm", cost="mid"),
   age_start=6, age_window="YLE 6-12 岁；KET/PET 约 9-12 岁",
   policy="caution",
   caution="三点务必分清：①'备考培训'属学科类培训（双减明确含外语），必须选持证合规机构，学龄前一律违规；②官方招生政策明确义务教育入学不得以考试证书为依据——'简历焦虑'的政策出口已经封死；③考级只是阶段检测，不是目标本身，以考代学会毁掉阅读兴趣。",
   note="英语路线分层新增；收录以给准确政策口径为主，家长搜索量极大。"),
 "线上英语课（外教）": dict(
   id="drama-english-online", aliases=["外教一对一", "线上英语", "网课英语"],
   summary="线上形态的英语培训：学龄前线上学科培训被明令禁止，学龄期须合规备案——市面上大量'外教1对1'实为不合规形态。",
   abilities={"expression": 1, "focus": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="mid"),
   age_start=6, age_window="仅学龄期考虑；学龄前线上英语属违规",
   policy="caution",
   caution="双减红线：不得开展面向学龄前儿童的线上培训；学龄期线上学科类培训须备案合规，且严禁聘请在境外的外籍人员开展培训——以此为滤镜看，'境外外教1对1'的主流宣传形态基本不合规，退费与跑路纠纷高发。屏幕时间另算。",
   note="英语路线分层新增；收录以避坑提示为主。"),
 # ---- 新兴手作/解压玩具类（2026-10-31：多为家庭/商场手作活动，非培训班赛道，如实标注）----
 "拼豆/串珠手作": dict(
   id="art-beads", aliases=["拼豆", "拼拼豆豆", "串珠", "手链编织"],
   summary="按图拼豆+熨烫定型的手作（商场手作店与家庭都常见）：图案规划+精细动作，成品可做杯垫挂饰。",
   abilities={"hands_on": 2, "focus": 2, "creativity": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="low"),
   age_start=4, age_window="4 岁+（小零件误吞风险，3 岁以下不适用）",
   family_ok=True,
   caution="小零件有误吞风险，低龄全程家长陪同；熨烫定型环节由家长操作。",
   note="新兴手作类新增；性质是家庭/体验活动，不存在'拼豆培训班'赛道。"),
 "史莱姆/起泡胶": dict(
   id="art-slime", aliases=["史莱姆", "起泡胶", "捏捏乐"],
   summary="解压玩具属性的捏塑玩物（不属课程）：孩子圈极流行，但安全红线必须知道。",
   abilities={"hands_on": 1, "creativity": 1},
   traits=dict(indoor="indoor", group="solo", tempo="calm", cost="low"),
   age_start=4, age_window="4 岁+，纯家庭玩乐",
   family_ok=True,
   policy="caution",
   caution="传统史莱姆配方含硼砂，误食或经伤口接触可致中毒与化学灼伤，多地监管部门曾多次提示；选无硼砂正规产品、家长陪同、避免入口揉眼、玩完洗手。'史莱姆课'基本不存在，商场体验注意卫生。",
   note="新兴手作类新增；玩具属性，收录以安全提示为主。"),
 # ---- 其他新兴/遗漏补充（2026-10-31）----
 "飞盘": dict(
   id="fitness-disc", aliases=["极限飞盘", "少儿飞盘"],
   summary="近年最出圈的新兴团队运动：无身体对抗、男女混场，跑动+接盘手眼协调，亲子友好。",
   abilities={"physical": 2, "social": 2, "focus": 1},
   traits=dict(indoor="outdoor", group="team", tempo="active", cost="low"),
   age_start=6, age_window="6 岁+软飞盘即可玩，少儿班在兴起",
   note="新兴运动新增；装备门槛极低，公园就能开始。"),
 "匹克球": dict(
   id="ball-pickleball", aliases=["Pickleball"],
   summary="网球+羽毛球+乒乓球的'三合一'缩小版：场地小、上手极快，全球增长最快的球拍运动之一，一线场馆正在铺开。",
   abilities={"physical": 2, "focus": 1, "social": 1},
   traits=dict(indoor="both", group="both", tempo="active", cost="mid"),
   age_start=6, age_window="行业惯例 6 岁+",
   note="新兴运动新增；与网球/乒乓球技能互通。"),
 "桥牌": dict(
   id="mind-bridge", aliases=["少年桥牌", "定约桥牌"],
   summary="四人两两配对的智力运动（智力运动会正式项目）：概率计算+搭档沟通，棋类之外的'社交型智力运动'。",
   abilities={"logic": 2, "social": 2, "focus": 1},
   traits=dict(indoor="indoor", group="both", tempo="calm", cost="low"),
   age_start=10, age_window="行业惯例 10 岁+（需配合约定体系）",
   note="棋牌家族补充；少年桥牌有全国性赛事体系。"),
 "宠物与生命教育": dict(
   id="life-pet", aliases=["养宠物", "宠物护理", "生命教育"],
   summary="不是培训班，是家庭生活方式：喂食、清理、记录、告别——责任感与生命观的最自然课堂。",
   abilities={"hands_on": 1, "social": 1, "resilience": 1},
   traits=dict(indoor="both", group="both", tempo="calm", cost="mid"),
   age_start=4, age_window="4 岁+从照顾小任务开始",
   family_ok=True,
   caution="选温顺品种、排查过敏；抓咬伤正确处理与狂犬疫苗常识家长必须掌握。",
   note="生活技能补充。"),
}
CATEGORY_BY_PREFIX = {c["id"]: c for c in CATEGORIES}

# ---------------------------------------------------------------- 移除清单（后期下架项目用）
# 用法：把要删除的项目 id（或名称）加进 REMOVE，重跑本脚本即从数据库移除。
# 例：REMOVE = {"ball-cricket"} 或 REMOVE = {"门球/地掷球"}
REMOVE = set()

# ---------------------------------------------------------------- 官方鼓励政策（2026-10-31 逐一核实；10-31晚补原文引述）
# quote 为逐字原句（经官方页面/权威转载核对）；quote_src 说明核验渠道；取不到逐字原句的宁可留空。
POLICIES = [
    {"id": "tijiao", "title": "《关于深化体教融合 促进青少年健康发展的意见》",
     "issuer": "体育总局、教育部（国办转发）", "year": 2020, "code": "体发〔2020〕1号",
     "url": "", "verified": "gov_policy库+体育总局官网原文",
     "gist": "鼓励青少年掌握运动技能，支持青少年体育俱乐部、体育传统特色学校建设，规范青少年体育技能培训发展。",
     "quote": "支持大中小学校建设学校代表队，成立青少年体育俱乐部。",
     "quote_src": "体育总局官网刊载原文（sport.gov.cn）"},
    {"id": "meiyu", "title": "《关于全面加强和改进新时代学校美育工作的意见》",
     "issuer": "中办、国办", "year": 2020, "code": "",
     "url": "https://www.gov.cn/zhengce/2020-10/15/content_5551609.htm", "verified": "gov.cn原文页",
     "gist": "开齐开足上好美育课程，以音乐、美术、书法、舞蹈、戏剧、影视等为主要内容，把美育纳入人才培养全过程。",
     "quote": "学校美育课程以艺术课程为主体，主要包括音乐、美术、书法、舞蹈、戏剧、戏曲、影视等课程。义务教育阶段丰富艺术课程内容，在开好音乐、美术、书法课程的基础上，逐步开设舞蹈、戏剧、影视等艺术课程。",
     "quote_src": "gov.cn 原文页逐字核对（2026-10-31）"},
    {"id": "laodong", "title": "《关于全面加强新时代大中小学劳动教育的意见》",
     "issuer": "中共中央、国务院", "year": 2020, "code": "",
     "url": "https://www.gov.cn/zhengce/2020-03/26/content_5495977.htm", "verified": "gov.cn原文页",
     "gist": "将劳动教育纳入人才培养全过程，明确清洁整理、烹饪等日常生活劳动与种植饲养、传统工艺制作等生产劳动的内容要求。",
     "quote": "以日常生活劳动、生产劳动和服务性劳动为主要内容开展劳动教育。……鼓励孩子自觉参与、自己动手，随时随地、坚持不懈进行劳动，掌握洗衣做饭等必要的家务劳动技能。",
     "quote_src": "gov.cn 原文页逐字核对（2026-10-31）"},
    {"id": "keli", "title": "《义务教育课程方案和课程标准（2022年版）》",
     "issuer": "教育部", "year": 2022, "code": "教材〔2022〕2号",
     "url": "", "verified": "gov_policy库+教育部答记者问",
     "gist": "劳动、信息科技独立设课；艺术课程包含音乐、美术、舞蹈、戏剧（含戏曲）与影视；信息科技课程涵盖编程等内容。",
     "quote": "改革艺术课程设置，一至七年级以音乐、美术为主线，融入舞蹈、戏剧、影视等内容，八至九年级分项选择开设。……将劳动、信息科技从综合实践活动课程中独立出来。",
     "quote_src": "教育部《义务教育课程方案和课程标准（2022年版）》答记者问（2022-04-21），多源转载逐字一致"},
    {"id": "kexue", "title": "《关于加强新时代中小学科学教育工作的意见》",
     "issuer": "教育部等十八部门", "year": 2023, "code": "教监管〔2023〕2号",
     "url": "http://www.moe.gov.cn/srcsite/A29/202305/t20230529_1061838.html", "verified": "moe.gov.cn原文页",
     "gist": "在教育'双减'中做好科学教育加法，鼓励广泛开展科学实验和科技实践活动。",
     "quote": "在教育'双减'中做好科学教育加法。",
     "quote_src": "教育部官网原文页（核心表述）"},
    {"id": "keji2025", "title": "《关于加强中小学科技教育的意见》",
     "issuer": "教育部等七部门", "year": 2025, "code": "教基〔2025〕7号",
     "url": "", "verified": "gov_policy库",
     "gist": "深入推进中小学科技教育，培养科技创新后备人才。",
     "quote": "到2030年，中小学科技教育体系基本建立。",
     "quote_src": "据官方发布与权威媒体报道的发展目标句"},
    {"id": "ai", "title": "《关于加强中小学人工智能教育的通知》",
     "issuer": "教育部办公厅", "year": 2024, "code": "教基厅函〔2024〕32号",
     "url": "https://peking.bjd.com.cn/content/s67596111e4b06b0a5624175e.html", "verified": "网络核实(官方报道)",
     "gist": "构建系统化中小学人工智能课程体系，分批设立中小学人工智能教育基地。",
     "quote": "构建系统化课程体系……探索中小学人工智能教育实施途径，实施常态化教学与评价。",
     "quote_src": "据教育部部署的权威媒体报道（北京日报/中国网教育频道）"},
    {"id": "zuqiu", "title": "《全国青少年校园足球八大体系建设行动计划》",
     "issuer": "教育部等七部门", "year": 2020, "code": "教体艺〔2020〕5号",
     "url": "", "verified": "gov_policy库",
     "gist": "大力普及校园足球，扩大青少年足球人口。",
     "quote": "高标准创建3万所校园足球特色学校，使校园足球特色学校总规模达到5万所，校园足球人口达到5000万以上。",
     "quote_src": "据文件印发的权威媒体报道（发展目标句）"},
    {"id": "bingxue", "title": "《关于加快推进全国青少年冰雪运动进校园的指导意见》",
     "issuer": "教育部等四部门", "year": 2019, "code": "教体艺〔2019〕3号",
     "url": "http://www.moe.gov.cn/srcsite/A17/moe_938/s3276/201906/t20190613_385735.html", "verified": "gov_policy库+moe原文页",
     "gist": "推动冰雪运动进校园，鼓励青少年掌握冰雪运动技能（'三亿人参与冰雪运动'）。",
     "quote": "加快发展青少年冰雪运动，丰富学校体育内容，提升青少年学生体质健康水平。",
     "quote_src": "据官方发布的文件主题句；发展目标为 2025 年冰雪运动特色学校达 5000 所"},
    {"id": "cujin", "title": "《青少年体育活动促进计划》",
     "issuer": "体育总局、教育部等七部门", "year": 2017, "code": "",
     "url": "https://www.sport.gov.cn/gdnps/html/zhengce/content.jsp?id=25530470", "verified": "官方直链（正文为附件下载）",
     "gist": "推动青少年体育活动普及，促进青少年掌握体育运动技能（2017-11 印发，2018-01 公开发布）。",
     "quote": "研究建立青少年运动技能等级评定标准。……各级教育部门应将运动技能等级纳入学生综合素质评价体系。",
     "quote_src": "据体育总局官网政策原文页（逐字句经检索核对）"},
    {"id": "jingshi", "title": "《综合防控儿童青少年近视实施方案》",
     "issuer": "教育部等八部门", "year": 2018, "code": "教体艺〔2018〕3号",
     "url": "http://www.moe.gov.cn/srcsite/A17/moe_943/s3285/201808/t20180830_346672.html", "verified": "官方直链",
     "gist": "引导孩子进行户外活动或体育锻炼，每天日间户外时间与近视防控直接挂钩。",
     "quote": "让孩子到户外阳光下度过更多时间，能够有效预防和控制近视。积极引导孩子进行户外活动或体育锻炼，使其在家时每天接触自然光时间达60分钟以上。",
     "quote_src": "方案'家庭'部分原句（多源转载逐字一致）"},
    {"id": "xiqu", "title": "《关于戏曲进校园的实施意见》",
     "issuer": "中宣部、教育部、财政部、文化部", "year": 2017, "code": "中宣发〔2017〕26号",
     "url": "https://www.waizi.org.cn/file/23037.html", "verified": "网络核实(全文转载)",
     "gist": "推进戏曲进校园，鼓励学校建设戏曲社团和兴趣小组。",
     "quote": "加强戏曲社团建设，支持学校建立多种类型的戏曲兴趣小组、学校戏曲社团、戏曲工作坊和戏曲传承基地等。",
     "quote_src": "全文转载页逐字核对（2026-10-31）"},
]

def _m(ids, pids):
    return {i: pids for i in ids}

MUSIC_IDS = ["music-orff", "music-djembe", "music-ukulele", "music-piano", "music-violin",
             "music-drums", "music-vocal", "music-erhu", "music-guzheng", "music-dizi",
             "music-pipa", "music-cello", "music-guitar", "music-wind", "music-brass",
             "music-choir", "music-production"]
ICE_IDS = ["ice-skating", "ice-skiing", "ice-figure", "ice-hockey", "ice-shorttrack",
           "ice-curling", "ice-snowboard"]

OFFICIAL_SUPPORT = {}
OFFICIAL_SUPPORT.update(_m(["ball-football"], ["tijiao", "zuqiu"]))
OFFICIAL_SUPPORT.update(_m(["ball-basketball", "ball-table-tennis", "ball-badminton", "ball-volleyball"], ["tijiao"]))
OFFICIAL_SUPPORT.update(_m(["water-swimming"], ["cujin"]))
OFFICIAL_SUPPORT.update(_m(ICE_IDS, ["bingxue"]))
OFFICIAL_SUPPORT.update(_m(["fitness-kids", "fitness-gymnastics"], ["tijiao"]))
OFFICIAL_SUPPORT.update(_m(["fitness-orienteering", "fitness-family-run", "nature-cycling", "nature-hiking"], ["jingshi"]))
OFFICIAL_SUPPORT.update(_m(["mind-scratch", "mind-robotics", "mind-coding"], ["keli"]))
OFFICIAL_SUPPORT.update(_m(["mind-robotics", "mind-coding"], ["ai"]))
OFFICIAL_SUPPORT.update(_m(["mind-ai"], ["ai"]))
OFFICIAL_SUPPORT.update(_m(["mind-maker", "mind-3dprint"], ["keji2025"]))
OFFICIAL_SUPPORT.update(_m(["mind-science"], ["kexue", "keji2025"]))
OFFICIAL_SUPPORT.update(_m(["nature-gardening", "life-baking", "art-woodcraft", "life-organizing"], ["laodong", "keli"]))
OFFICIAL_SUPPORT.update(_m(MUSIC_IDS, ["meiyu"]))
OFFICIAL_SUPPORT.update(_m(["dance-street", "dance-jazz", "dance-modern", "dance-tap"], ["meiyu"]))
OFFICIAL_SUPPORT.update(_m(["art-creative", "art-chinese-painting", "art-calligraphy", "art-painting"], ["meiyu"]))
OFFICIAL_SUPPORT.update(_m(["drama-drama"], ["meiyu"]))
OFFICIAL_SUPPORT.update(_m(["drama-jingju", "drama-qinqiang"], ["meiyu", "xiqu"]))

# policy 升级为 encouraged 的项目（有官方文件明确鼓励）。
# 注意：policy=caution（年龄/安全红线）的项目不升级——红线优先于鼓励，official_support 照常记录。
ENCOURAGE_IDS = set(OFFICIAL_SUPPORT.keys()) - {"art-sketch", "dance-chinese", "dance-ballet",
                                                "dance-latin", "ice-figure"}

# ---------------------------------------------------------------- 标签二审（2026-10-31 第二轮自查）
# 逐条审查发现的问题：①约 15 个项目只有权重 1 的标签、没有"主要培养"方向，前端无法突出重点——补主标签；
# ②舞蹈类体能权重偏低（舞蹈本质是身体训练）——physical 升为 2；③个别标签缺项。键为条目 id，整组覆盖 abilities。
TAG_AUDIT = {
    "ball-bowling": {"logic": 2, "physical": 1, "social": 1},
    "combat-taichi": {"focus": 2, "physical": 1},
    "water-diving-exp": {"focus": 2, "physical": 1},
    "ball-gateball": {"focus": 2, "physical": 1},
    "art-sand": {"creativity": 2, "aesthetic": 1, "hands_on": 1},
    "mind-financial": {"logic": 2, "hands_on": 1, "focus": 1},
    "life-allowance": {"logic": 2, "focus": 1},
    "life-organizing": {"hands_on": 2, "logic": 1, "focus": 1},
    "mind-stacking": {"hands_on": 2, "focus": 1, "physical": 1},
    "mind-geography": {"logic": 2, "hands_on": 1, "focus": 1},
    "life-pet": {"hands_on": 2, "social": 1, "resilience": 1},
    "nature-museum": {"focus": 2, "logic": 1, "aesthetic": 1},
    "nature-forest": {"logic": 2, "focus": 1, "hands_on": 1, "physical": 1, "creativity": 1},
    "nature-hiking": {"hands_on": 2, "resilience": 1, "social": 1, "physical": 1},
    "nature-insects": {"focus": 2, "logic": 1, "hands_on": 1},
    "drama-puppet": {"aesthetic": 2, "hands_on": 1, "creativity": 1},
    "drama-model": {"expression": 2, "physical": 1, "social": 1},
    "fitness-family-run": {"physical": 2, "social": 1},
    "mind-esports": {"focus": 2, "logic": 1, "resilience": 1},
    "art-slime": {"hands_on": 2, "creativity": 1},
    "life-tea": {"aesthetic": 2, "focus": 1, "social": 1},
    # 第二轮漏网补漏（2026-10-31 晚）
    "water-parent-swim": {"physical": 2, "social": 1},
    "mind-space": {"logic": 2, "focus": 1, "hands_on": 1, "creativity": 1},
    # 规则：警示型条目（banned/discouraged/pseudoscience 及纯避坑项）不设主标签，保留权重 1 即可
    # 舞蹈类：体能权重升为 2（舞蹈是身体训练，不只审美）
    "dance-street": {"physical": 2, "aesthetic": 2, "expression": 1, "resilience": 1},
    "dance-chinese": {"physical": 2, "aesthetic": 2, "expression": 1, "resilience": 1},
    "dance-ballet": {"physical": 2, "aesthetic": 2, "expression": 1, "focus": 1},
    "dance-latin": {"physical": 2, "aesthetic": 2, "expression": 1},
    "dance-jazz": {"physical": 2, "aesthetic": 2, "expression": 1},
    "dance-modern": {"physical": 2, "aesthetic": 2, "expression": 1},
    "dance-tap": {"aesthetic": 2, "physical": 2, "focus": 1},
}

# ---------------------------------------------------------------- 资源热度（四级，2026-10-31 全库标注）
# hot=热门（全国普及，几乎所有城市可报）；warm=常见（多数城市可找到）；
# cool=小众（一二线城市才有稳定供给）；rare=稀缺（基本无稳定少儿培训体系，了解/体验为主）。
HEAT_DEFAULTS = {"ball": "warm", "water": "cool", "ice": "cool", "fitness": "warm", "combat": "warm",
                 "mind": "warm", "music": "warm", "dance": "warm", "drama": "warm", "art": "warm",
                 "nature": "warm", "life": "warm"}
HEAT = {
    # hot（覆盖默认值）
    "ball-basketball": "hot", "ball-football": "hot", "ball-table-tennis": "hot", "ball-badminton": "hot",
    "water-swimming": "hot", "fitness-kids": "hot", "fitness-rope": "hot", "fitness-roller": "hot",
    "combat-taekwondo": "hot", "mind-lego": "hot", "mind-math": "hot", "mind-preschool-academic": "hot",
    "drama-english": "hot", "drama-english-cambridge": "hot", "music-piano": "hot",
    "dance-street": "hot", "dance-chinese": "hot", "drama-speech": "hot",
    "art-creative": "hot", "art-calligraphy": "hot", "art-sketch": "hot", "nature-cycling": "hot",
    # cool
    "ball-baseball": "cool", "ball-flag-football": "cool", "ball-handball": "cool", "ball-squash": "cool",
    "ball-golf": "cool", "ball-billiards": "cool", "ball-bowling": "cool", "ball-kabaddi": "cool",
    "ball-sepak-takraw": "cool", "ball-pickleball": "cool", "ball-padel": "cool",
    "water-artistic": "cool", "water-kayak": "cool", "water-sup": "cool", "water-sailing": "cool",
    "water-diving-exp": "cool", "water-dragon-boat": "cool", "water-surfing": "cool",
    "ice-figure": "cool", "ice-hockey": "cool", "ice-snowboard": "cool",
    "fitness-parkour": "cool", "fitness-orienteering": "cool", "fitness-bmx": "cool",
    "fitness-karting": "cool", "fitness-kids-athletics": "cool", "fitness-athletics": "cool",
    "fitness-disc": "cool", "fitness-weightlifting": "cool",
    "combat-fencing": "cool", "combat-kendo": "cool", "combat-bjj": "cool", "combat-boxing": "cool",
    "combat-wrestling": "cool", "combat-laser-shot": "cool",
    "mind-checkers": "cool", "mind-aero-model": "cool", "mind-drone": "cool", "mind-ai": "cool",
    "mind-maker": "cool", "mind-3dprint": "cool", "mind-bridge": "cool",
    "music-wind": "cool", "music-brass": "cool", "music-choir": "cool", "music-production": "cool",
    "music-accordion": "cool", "music-yangqin": "cool", "music-ruan": "cool", "music-guqin": "cool",
    "music-mallet": "cool",
    "dance-modern": "cool", "drama-crosstalk": "cool", "drama-jingju": "cool", "drama-qinqiang": "cool",
    "drama-puppet": "cool", "drama-bilingual": "cool", "drama-l2": "cool", "drama-dubbing": "cool",
    "drama-model": "cool", "drama-english-online": "cool",
    "art-woodcraft": "cool", "art-sand": "cool", "art-illustration": "cool", "art-print": "cool",
    "art-seal": "cool", "art-digital": "cool", "art-video": "cool",
    "nature-forest": "cool", "nature-camp": "cool", "nature-equestrian": "cool",
    "life-tea": "cool", "life-first-aid": "cool", "mind-right-brain": "cool",
    # rare
    "ball-cricket": "rare", "ball-gateball": "rare",
    "water-diving": "rare", "water-polo": "rare", "water-rowing": "rare", "water-finswim": "rare",
    "ice-shorttrack": "rare", "ice-curling": "rare",
    "fitness-triathlon": "rare", "fitness-pentathlon": "rare",
    "combat-kurash": "rare", "combat-mma": "rare",
    "mind-ship-model": "rare", "mind-radio": "rare",
    "music-suona": "rare", "music-sheng": "rare", "music-harp": "rare", "music-double-bass": "rare",
    "dance-tap": "rare", "nature-rafting": "rare",
}


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


ENRICH_BY_NORM = {norm(k): v for k, v in E.items()}


# ---------------------------------------------------------------- 年龄解析

def parse_age(text: str):
    """返回 (age_start, age_stop)；解析不出数字时 (None, None)。"""
    t = text.replace("岁半", ".5岁")
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", t)]
    if not nums:
        return None, None
    start = min(nums)
    stop = None
    max_n = max(nums)
    # 低龄窗口型项目（0-4、2-4）或明确标注"窗口"
    if len(nums) >= 2 and (("窗口" in text) or (start <= 2 and max_n <= 4)):
        stop = max_n
    return start, stop


def tier_from_refs(refs, src_text):
    best = "industry"
    for r in refs:
        t = SOURCE_TIER.get(r)
        if t and TIER_RANK[t] > TIER_RANK[best]:
            best = t
    if not refs:
        # 无引用编号的条目：行业惯例或无依据
        best = "industry"
    return best


# ---------------------------------------------------------------- 主流程

def main():
    with open(HTML_PATH, encoding="utf-8") as f:
        html = f.read()
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "details.json"), encoding="utf-8") as f:
        DETAILS = json.load(f)
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "age_verification.json"), encoding="utf-8") as f:
        AGE_VER = json.load(f)
    AGE_VER_MAP = {x["id"]: x for x in AGE_VER["items"]}
    p = ListParser()
    p.feed(html)

    # 大类标题 → category id
    cat_ids = []
    for sec in p.sections:
        title = sec["title"]
        # 标题形如 "一、球类运动" / "引用信源清单"
        core = re.sub(r"^[一二三四五六七八九十]+、", "", title).strip()
        matched = None
        for c in CATEGORIES:
            if norm(c["name"]) in norm(core) or norm(core).startswith(norm(c["name"])):
                matched = c["id"]
                break
        cat_ids.append((sec, matched))

    activities = []
    problems = []
    used_ids = set()
    personal = {}   # 个性化字段存档（gitignored，不入公开仓库）

    for sec, cat_id in cat_ids:
        if cat_id is None:
            continue  # 信源清单等非项目 section
        for row in sec["rows"]:
            name = strip_chg_words(row["name"])
            key = norm(name)
            enrich = ENRICH_BY_NORM.get(key)
            if enrich is None:
                problems.append(f"[缺ENRICH] {name!r} (section={sec['title']})")
                continue
            aid = enrich["id"]
            if aid in used_ids:
                problems.append(f"[id重复] {aid} <- {name}")
            used_ids.add(aid)

            badge_m = re.search(r"\bb([0-5])\b", row.get("badge_cls", "") or "")
            badge_level = int(badge_m.group(1)) if badge_m else None
            badge_text = row.get("badge_text", "").strip() or BADGE_TEXT_FALLBACK

            age_start, age_stop = parse_age(row["age"])
            # ENRICH 可显式覆盖自动解析结果（用于文本歧义，如"9岁+（8岁前红线维持）"）
            if "age_start" in enrich:
                age_start = enrich["age_start"]
            if "age_stop" in enrich:
                age_stop = enrich["age_stop"]

            # policy：ENRICH 显式 > b0 强制检查 > badge 默认 > 官方鼓励升级
            policy = enrich.get("policy")
            if policy is None:
                if badge_level == 0:
                    problems.append(f"[b0未定policy] {name}")
                    policy = "caution"
                else:
                    policy = "normal"
            if policy == "normal" and aid in ENCOURAGE_IDS:
                policy = "encouraged"

            family_ok = enrich.get("family_ok", badge_level == 2)

            refs = sorted({("r31" if r == "r12" else r) for r in row["refs"]}, key=lambda r: int(r[1:]))
            tier = tier_from_refs(refs, row["src"])

            act = {
                "id": aid,
                "name": enrich.get("display_name") or name,
                "aliases": [a for a in enrich.get("aliases", []) if a and a.strip()],
                "category": cat_id,
                "summary": enrich["summary"],
                "age_start": age_start,
                "age_stop": age_stop,
                "age_window": row["age"],
                "abilities": TAG_AUDIT.get(aid, enrich.get("abilities", {})),
                "traits": enrich["traits"],
                "detail": DETAILS.get(aid),
                "age_check": (lambda v: ({"level": "verified", "n": len(v["sources"]), "sources": v["sources"]} if v else None))(AGE_VER_MAP.get(aid)),
                "heat": HEAT.get(aid, HEAT_DEFAULTS.get(cat_id, "warm")),
                "policy": policy,
                "caution": enrich.get("caution"),
                "gender_note": enrich.get("gender_note"),
                "family_ok": bool(family_ok),
                "source_refs": refs,
                "source_tier": tier,
                "official_support": OFFICIAL_SUPPORT.get(aid, []),   # 引用 policies.json 的文件 id
                "status": enrich.get("status", "active"),
            }
            # 个性化字段不入 activities.json（公开仓库），写独立存档 personal_archive.json（gitignored）
            personal[aid] = {
                "badge_original": badge_text,
                "detail_original": row["why"],   # 原定制清单推荐理由（含个性化措辞）
                "source_original": row["src"],   # 原信源摘记
                "verified_at": TODAY,
                "notes": enrich.get("note"),
            }
            activities.append(act)

    # ---- 新增条目（不在原 HTML 中，仅存在于 ENRICH，如本轮审核新增项）----
    for name, enrich in E.items():
        aid = enrich["id"]
        if aid in used_ids:
            continue
        cat_id = aid.split("-")[0]
        if cat_id not in CATEGORY_BY_PREFIX:
            problems.append(f"[新增条目分类未知] {name} ({aid})")
            continue
        policy = enrich.get("policy", "normal")
        if policy == "normal" and aid in ENCOURAGE_IDS:
            policy = "encouraged"
        refs = sorted(set(enrich.get("refs", [])), key=lambda r: int(r[1:]))
        activities.append({
            "id": aid,
            "name": name,
            "aliases": [a for a in enrich.get("aliases", []) if a and a.strip()],
            "category": cat_id,
            "summary": enrich["summary"],
            "age_start": enrich.get("age_start"),
            "age_stop": enrich.get("age_stop"),
            "age_window": enrich.get("age_window", "本轮新增条目，无原文年龄栏"),
            "abilities": TAG_AUDIT.get(aid, enrich.get("abilities", {})),
            "traits": enrich["traits"],
            "detail": DETAILS.get(aid),
            "age_check": (lambda v: ({"level": "verified", "n": len(v["sources"]), "sources": v["sources"]} if v else None))(AGE_VER_MAP.get(aid)),
                "heat": HEAT.get(aid, HEAT_DEFAULTS.get(cat_id, "warm")),
            "policy": policy,
            "caution": enrich.get("caution"),
            "gender_note": enrich.get("gender_note"),
            "family_ok": bool(enrich.get("family_ok", False)),
            "source_refs": refs,
            "source_tier": tier_from_refs(refs, ""),
            "official_support": OFFICIAL_SUPPORT.get(aid, []),
            "status": enrich.get("status", "active"),
        })
        personal[aid] = {
            "badge_original": "新增（本轮审核）",
            "detail_original": None,
            "source_original": None,
            "verified_at": TODAY,
            "notes": enrich.get("note"),
        }

    # ---- 移除清单过滤（后期下架项目用，见 REMOVE 定义处说明）----
    before = len(activities)
    activities = [a for a in activities if a["id"] not in REMOVE and a["name"] not in REMOVE]
    if len(activities) < before:
        print(f"按 REMOVE 清单移除 {before - len(activities)} 项")

    # ---- 输出 ----
    os.makedirs(OUT_DIR, exist_ok=True)

    # 信源改造（2026-10-31）：清退渠道型信源（r12 绵阳市少年宫），升级弱载体，
    # 全部对齐"国家级以上机构 / 严肃媒体 / 学术著作"标准；r31 为本轮新增。
    REF_REMAP = {"r12": "r31"}          # 引用重定向：原 r12 的条目改引 r31
    SOURCE_SKIP = {"r12"}
    SOURCE_OVERRIDES = {
        "r1": {"url": "http://www.moe.gov.cn/srcsite/A06/s3325/201210/t20121016_143254.html",
               "excerpt": "教育部官方文件（moe.gov.cn 原文页）：幼儿每天户外活动≥2小时、体育活动≥1小时；学习方式'直接感知、亲身体验、实际操作'；科学领域'经常带幼儿接触大自然'。"},
        "r11": {"title": "罗恩菲德《创造性与心智成长》儿童绘画六阶段（学术著作）",
                "excerpt": "学术理论：涂鸦期2-4岁→前图式期4-7岁→图式期7-9岁→写实萌芽期9-11岁——写实/素描训练对应9岁后。理论载体见光明日报 2023-07-21《学美术一定要从学素描开始吗》（r31）。",
                "url": "https://epaper.gmw.cn/gmrb/html/2023-07/21/nw.D110000gmrb_20230721_2-07.htm"},
        "r18": {"title": "器乐启蒙年龄：行业通例（多来源交叉的通行口径，非官方文件）",
                "excerpt": "钢琴约 5 岁（手指力量与坐姿专注具备后）、小提琴 5-6 岁（铃木体系惯例可 3-4 岁，须家长全程陪练）、管乐等换牙后 7-9 岁起——为多家音乐学院附中/培训机构与育儿科普反复出现的通行口径，经多来源交叉一致；未见教育部/卫健委层面官方年龄文件，故如实标注为行业口径。"},
    }
    # r16 改造：原引新民晚报调查（地方媒体），其权威内核是 2026-09-01 实施的强制国标，
    # 现直接引国标本体（openstd 官方公开系统）；"6-7岁/1.2米"行业底线保留在条目 caution 中，不挂国标名义。
    SOURCE_OVERRIDES["r16"] = {"tier": "official",
        "title": "强制国标《体育场所开放条件与技术要求 第2部分：卡丁车场所》（GB 19079.2-2026）",
        "excerpt": "强制性国家标准，2026-02-27 发布、2026-09-01 实施（替代 GB 19079.2-2005 等三项旧标准）：要求配套缓冲带/防撞墙/防护网等安全设施，驾驶人员佩戴全盔（带护目镜）、防护服覆盖躯干/脖颈/四肢，14 周岁及以下使用带护胸板护肋装置的卡丁车。业内通行的独立驾驶底线约 6-7 岁/身高 1.2 米为行业口径，非国标条文。",
        "url": "https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=9462BEA917E1F04BB6F1A9E76C64A7E5"}
    SOURCE_OVERRIDES["r23"] = {"url": "http://china.cnr.cn/xwygd/20200909/t20200909_525248223_1.shtml",
        "title": "央广网·中国之声《教育部将研究珠算文化进小学 业界争论仍未休止》（2020-09）",
        "excerpt": "国家级广播电台：中科院脑科学博士陆宇斐在中国之声《新闻有观点》专访中表示，珠心算是模式化、机械化的技巧训练，压缩甚至直接忽略思考过程；因运算规则不同，儿童过早接触会对其理解十进制产生冲突，影响抽象思维的形成和后期数学学习。"}
    SOURCE_OVERRIDES["r26"] = {"title": "科普中国（中国科协）发布《“全脑开发”“量子速读”是伪科学骗局》，中国网/中国新闻网转载（2026-05）",
        "excerpt": "国家级科普平台定性：打着“全脑开发”“量子速读”旗号的培训班为伪科学骗局，并给出官方查证渠道；中国网、中国新闻网等转载。"}
    EXTRA_SOURCES = [{"id": "r31", "tier": "authority",
        "title": "光明日报《学美术一定要从学素描开始吗》（2023-07-21）",
        "excerpt": "严肃媒体（中共中央机关报）：少儿过早学习素描不但没有好处反而有害，素描的基本要素需要心智达到一定程度的成长方能理解。",
        "url": "https://epaper.gmw.cn/gmrb/html/2023-07/21/nw.D110000gmrb_20230721_2-07.htm"}]
    sources = []
    seen_ids = set()
    for r in sorted(p.refs, key=lambda x: int(x["id"][1:])):
        rid = r["id"]
        if rid in SOURCE_SKIP:
            continue
        rid_out = REF_REMAP.get(rid, rid)
        if rid_out in seen_ids:
            continue
        seen_ids.add(rid_out)
        ov = SOURCE_OVERRIDES.get(rid_out, {})
        sources.append({
            "id": rid_out,
            "tier": ov.get("tier", SOURCE_TIER.get(rid_out, "industry")),
            "title": ov.get("title", r.get("title") or ""),
            "excerpt": ov.get("excerpt", r.get("text", "")),
            "url": ov.get("url", r.get("url", "")),
        })
    for extra in EXTRA_SOURCES:
        if extra["id"] not in seen_ids:
            sources.append(extra)
            seen_ids.add(extra["id"])
    sources.sort(key=lambda s: int(s["id"][1:]))

    meta = {
        "version": "1.2.0",
        "generated_at": TODAY,
        "provenance": "提取自《儿童兴趣班全景清单（权威修订版）》2026-10-23 第2版（私人定制版），"
                      "含个性化措辞的原推荐理由等字段已拆分至 personal_archive.json（gitignored，不入公开仓库）；"
                      "官方鼓励维度依据 policies.json（2026-10-31 逐一核实）接入；"
                      "体育类完备性以 2026 爱知名古屋亚运会 43 个大项为基准逐项对照（大项入表、小项进别名）；"
                      "艺术类完备性按音乐六家族（键盘/弦乐/民乐/管乐/打击乐/电声）与美术四门类（绘画/立体/工艺/数字）盘点补齐；"
                      "科技类完备性按编程AI/机器人硬件/模型/科学观察/思维五条线盘点补齐；"
                      "英语路线按'家庭磨耳朵/绘本阅读、线上外教形态、剑桥考级认证'三层如实收录并标明政策状态；"
                      "新兴手作（拼豆/史莱姆）按'体验活动非培训班'属性收录并带安全提示；"
                      "内容丰富 v1.1：199 项全部带项目介绍（大众项讲优点与特质，小众项先讲是什么）；年龄核验台账 age_verification.json（第 1 轮：15 个高频项完成多源交叉核验）；"
                      "主题纪律：只收录与兴趣班/特长班直接相关的内容——独立'反面机构'条目（视力康复/增高/网瘾特训等非兴趣班形态）"
                      "经用户确认移除，关键安全红线保留在对应兴趣条目的 caution 内（骑行12岁上路、禁止野泳、蹦床6岁、拳击头部击打等）",
        "counts": {
            "activities": len(activities),
            "sources": len(sources),
            "policies": len(POLICIES),
        },
    }

    with open(os.path.join(OUT_DIR, "activities.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "activities": activities}, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT_DIR, "personal_archive.json"), "w", encoding="utf-8") as f:
        json.dump({"_说明": "个性化字段存档（原私人定制清单推荐理由等），仅本地留存，gitignore，不入公开仓库", "items": personal}, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT_DIR, "sources.json"), "w", encoding="utf-8") as f:
        json.dump(sources, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT_DIR, "policies.json"), "w", encoding="utf-8") as f:
        json.dump(POLICIES, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT_DIR, "categories.json"), "w", encoding="utf-8") as f:
        json.dump(CATEGORIES, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT_DIR, "abilities.json"), "w", encoding="utf-8") as f:
        json.dump(ABILITIES, f, ensure_ascii=False, indent=2)

    # ---- 报告 ----
    by_cat = {}
    for a in activities:
        by_cat[a["category"]] = by_cat.get(a["category"], 0) + 1
    by_policy = {}
    for a in activities:
        by_policy[a["policy"]] = by_policy.get(a["policy"], 0) + 1
    by_tier = {}
    for a in activities:
        by_tier[a["source_tier"]] = by_tier.get(a["source_tier"], 0) + 1
    no_age = [a["name"] for a in activities if a["age_start"] is None and a["status"] == "active"
              and a["policy"] not in ("discouraged", "pseudoscience", "redline", "banned_preschool")]

    print("=" * 60)
    print(f"项目总数: {len(activities)}   信源: {len(sources)} 条")
    print("分类分布:", json.dumps(by_cat, ensure_ascii=False))
    print("政策分布:", json.dumps(by_policy, ensure_ascii=False))
    print("证据等级:", json.dumps(by_tier, ensure_ascii=False))
    print(f"家庭即可开展: {sum(1 for a in activities if a['family_ok'])} 项")
    print(f"active 且无年龄数据（需人工补）: {no_age}")
    if problems:
        print("\n!!! 问题清单:")
        for x in problems:
            print("  ", x)
        sys.exit(1)
    print("\nOK -> data/activities.json, sources.json, categories.json, abilities.json")


if __name__ == "__main__":
    main()
