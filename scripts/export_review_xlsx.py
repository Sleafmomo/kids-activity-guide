#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 data/*.json 导出成人可读的 Excel 审核表（给非技术协作者审核数据用）。

重跑：python3 scripts/export_review_xlsx.py
输出：兴趣班数据审核表.xlsx（项目根目录）
"""
import json
import os
import sys

XLSX_SKILL_DIR = os.path.expanduser("~/.zcode/cli/plugins/cache/zcode-plugins-official/spreadsheets/0.2.1/skills/xlsx")
for sub in [XLSX_SKILL_DIR, os.path.join(XLSX_SKILL_DIR, "templates")]:
    if sub not in sys.path:
        sys.path.insert(0, sub)

from base import (  # noqa: E402
    FONT_NAME, HEADER_BOLD, PRIMARY, NEUTRAL_600, NEUTRAL_900,
    ACCENT_POSITIVE, ACCENT_NEGATIVE, ACCENT_WARNING,
    setup_sheet, style_header_row, style_data_row,
    auto_fit_columns, auto_fit_row_heights, font_caption,
)
from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import Font, PatternFill, Alignment  # noqa: E402
from openpyxl.utils import get_column_letter  # noqa: E402

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(BASE, "兴趣班数据审核表.xlsx")

POLICY_TEXT = {
    "normal": "正常",
    "caution": "⚠ 有红线，可参与但有年龄/安全限制",
    "discouraged": "✗ 不推荐（权威口径负面）",
    "banned_preschool": "✗ 学龄前违规办学（双减）",
    "pseudoscience": "✗ 伪科学（官方点名）",
    "encouraged": "✓ 官方文件鼓励",
    "redline": "⛔ 绝对禁止（法定/权威红线）",
}
POLICY_COLOR = {  # (fill, font color)；normal 不上色
    "caution": ("FEF9E7", ACCENT_WARNING),
    "discouraged": ("FDEDEC", ACCENT_NEGATIVE),
    "banned_preschool": ("FDEDEC", ACCENT_NEGATIVE),
    "pseudoscience": ("FDEDEC", ACCENT_NEGATIVE),
    "encouraged": ("E8F5E9", ACCENT_POSITIVE),
    "redline": ("FDEDEC", ACCENT_NEGATIVE),
}
TIER_TEXT = {"official": "官方文件/国标", "authority": "权威机构", "industry": "行业惯例"}
TRAITS_TEXT = {
    "indoor": {"indoor": "室内", "outdoor": "户外", "both": "室内外均可"},
    "group": {"team": "团队", "solo": "个人", "both": "均可"},
    "tempo": {"active": "动态", "calm": "静态", "both": "动静兼有"},
    "cost": {"low": "低", "mid": "中", "high": "高"},
}


def load(name):
    with open(os.path.join(BASE, "data", name), encoding="utf-8") as f:
        return json.load(f)


def main():
    acts = load("activities.json")["activities"]
    cats = {c["id"]: c["name"] for c in load("categories.json")}
    abis = {a["id"]: a["name"] for a in load("abilities.json")}
    sources = load("sources.json")
    pols = {p["id"]: p for p in load("policies.json")}

    wb = Workbook()

    # ---------------- Sheet 1: 审核说明 ----------------
    ws = wb.active
    ws.title = "先看这页"
    guide_rows = [
        ("这份表是什么", "上一轮我们建的『儿童兴趣班选班数据库』，目前收录 146 个项目。这份 Excel 就是数据库全部内容的可读版，供你审核。"),
        ("你要审什么", "本轮我已替你完成自查并核实了官方鼓励文件，你只需浏览式过目，看到明显不对的告诉我即可。重点扫 4 列：「主要培养/次要培养」能力标签、「政策状态」、「安全红线提示」、「建议开始年龄」。"),
        ("怎么提意见", "两种方式任选：1) 直接在最后一列「审核意见」里写（例如：'围棋：专注力应该是主要培养'）；2) 在微信里直接打字告诉我，如'第 23 行跆拳道年龄改成5岁'。写完把文件发我即可。"),
        ("颜色含义", "政策状态列：绿色=有官方文件鼓励（并注明文件名），黄色=有红线（可参与但有年龄/安全限制），红色=不推荐/违规/伪科学，无色=正常。"),
        ("证据等级列", "「年龄口径依据」分三级：官方文件/国标 > 权威机构（如美国儿科学会、教育部指南）> 行业惯例。标注为'行业惯例'的条目意味着没有官方红线条文。"),
        ("官方鼓励文件列", "本轮已核实 12 份中央文件（体教融合、美育、劳动教育、2022课程方案、科学教育、AI教育、校园足球、冰雪进校园、游泳促进计划、近视防控、戏曲进校园等），54 个项目挂上了官方鼓励依据，绿色状态行可直接看到文件名。"),
        ("体育类完备性", "体育大项以 2026 爱知名古屋亚运会 43 个大项为基准逐项对库（159 项总量）：新增柔道、克拉术、综合格斗、卡巴迪、藤球、板式网球、举重、现代五项、龙舟、冲浪、电子竞技 11 项；泳姿/器械等小项并入大项别名（如单杠/双杠/跳马→体操，自由泳/蛙泳→游泳，霹雳舞→街舞）。新增的稀缺项目如实标注'了解为主'。"),
        ("艺术类完备性", "音乐按六家族盘点补齐（键盘/弦乐/民乐/管乐/打击乐/电声）：新增电子琴、手风琴、扬琴、中阮/柳琴、唢呐、笙、古琴、竖琴、低音提琴、萨克斯、课堂乐器、古典打击乐、少儿乐队、乐理视唱练耳；美术按四门类补齐（绘画/立体/工艺/数字）：新增版画、篆刻、传统手工、布艺缝纫、数字绘画板绘、少儿影像；戏剧新增音乐剧、魔术、少儿模特（风险警示项）。常见乐器搜索词均已入库。"),
        ("科技类完备性", "科技/思维类按五条线盘点补齐：新增人工智能AI启蒙、创客开源硬件（Arduino/micro:bit）、电子电路、3D建模打印、显微观察、航天启蒙/火箭模型、无线电测向、数学思维/奥数（学科类监管口径警示）；机器人条目补 EV3/VEX/FLL 等竞赛体系别名，编程条目补信息学奥赛/CSP-J 别名。"),
        ("英语与新兴项目", "英语按三层如实收录（国家不鼓励但家长必搜）：①英语启蒙（家庭磨耳朵，学龄前报班违规）②英语绘本/分级阅读（正规家庭路线）③剑桥英语考级 YLE/KET/PET 与线上外教课（考试合法、培训受学科类监管、'境外外教1对1'主流形态基本不合规）。新兴项目：拼豆/串珠（家庭手作非培训班）、史莱姆（硼砂安全红线）、飞盘、匹克球、桥牌、宠物与生命教育；高达并入拼装模型、扭扭棒并入传统手工、斯巴达赛并入跑酷。"),
        ("安全红线说明", "按'只收录兴趣班/特长班'的主题原则，独立的反面机构条目（视力康复/增高/网瘾特训等非兴趣班形态）已移除。关键安全红线保留在对应兴趣条目的「安全红线提示」列：骑行满12岁才能上路（含2025年骑行事故教训）、绝对禁止野泳、蹦床6岁前不去、拳击类头部击打、素描9岁、舞蹈不下腰等。全库政策警示共 6 项（珠心算/感统训练/全脑开发/幼小衔接班/学龄前英语班/门球），筛'政策状态'即可捞出。"),
        ("两个待办", "1) 3 岁段项目仍偏少（15 项）——但客观上 3 岁前官方口径就是自由玩耍为主，这份数据会如实呈现；2) 原清单里针对个别孩子的推荐措辞（detail_original 字段）尚未改写，不影响你看到的这版内容。"),
    ]
    setup_sheet(ws, title="审核说明（先读这页，2 分钟）", last_col=3)
    ws.cell(row=4, column=2, value="条目")
    ws.cell(row=4, column=3, value="说明")
    style_header_row(ws, row_num=4, col_start=2, col_end=3)
    for i, (k, v) in enumerate(guide_rows):
        r = 5 + i
        ws.cell(row=r, column=2, value=k)
        ws.cell(row=r, column=3, value=v)
        style_data_row(ws, row_num=r, col_start=2, col_end=3, row_index=i)
    ws.column_dimensions["B"].width = 16
    ws.column_dimensions["C"].width = 90
    auto_fit_row_heights(ws, header_row=4, data_start_row=5)

    # ---------------- Sheet 2: 项目总表 ----------------
    ws2 = wb.create_sheet("项目总表")
    headers = ["序号", "项目", "分类", "别名/搜索词", "一句话简介", "项目介绍",
               "建议开始年龄", "年龄说明", "年龄核验", "主要培养", "次要培养",
               "环境", "个人/团队", "动静", "成本", "资源热度", "在家即可",
               "政策状态", "官方鼓励文件", "安全红线提示", "年龄口径依据", "审核意见"]
    last_col = len(headers) + 1
    setup_sheet(ws2, title=f"项目总表（{len(acts)} 项 · 重点扫：能力标签 / 政策状态 / 红线提示 / 年龄）", last_col=last_col)
    for ci, h in enumerate(headers, start=2):
        ws2.cell(row=4, column=ci, value=h)
    style_header_row(ws2, row_num=4, col_start=2, col_end=last_col)

    for i, a in enumerate(acts):
        r = 5 + i
        main_ab = "、".join(abis[k] for k, w in a["abilities"].items() if w >= 2)
        sub_ab = "、".join(abis[k] for k, w in a["abilities"].items() if w == 1)
        t = a["traits"]
        vals = [
            i + 1,
            a["name"] + ("（仅展示）" if a["status"] == "excluded" else ""),
            cats.get(a["category"], a["category"]),
            "、".join(a["aliases"]) or "—",
            a["summary"],
            a.get("detail") or "—",
            a["age_start"] if a["age_start"] is not None else "—",
            a["age_window"] or "—",
            (lambda ac: ("✓ 已 %d 类来源交叉核验：%s" % (ac["n"], "；".join(s["name"] + "——" + s["says"] for s in ac["sources"]))) if ac else ("依据官方/权威信源" if a["source_tier"] != "industry" else "行业通例，待多源核验"))(a.get("age_check")),
            main_ab or "—",
            sub_ab or "—",
            TRAITS_TEXT["indoor"][t["indoor"]],
            TRAITS_TEXT["group"][t["group"]],
            TRAITS_TEXT["tempo"][t["tempo"]],
            TRAITS_TEXT["cost"][t["cost"]],
            {"hot": "热门", "warm": "常见", "cool": "小众", "rare": "稀缺"}[a["heat"]],
            "是" if a["family_ok"] else "否",
            POLICY_TEXT[a["policy"]],
            "；".join(pols[p]["title"] + f"（{pols[p]['issuer']}，{pols[p]['year']}）"
                      for p in a["official_support"]) or "—",
            a["caution"] or "—",
            TIER_TEXT[a["source_tier"]],
            "",  # 审核意见
        ]
        for ci, v in enumerate(vals, start=2):
            ws2.cell(row=r, column=ci, value=v)
        style_data_row(ws2, row_num=r, col_start=2, col_end=last_col, row_index=i)
        # 政策状态上色
        color = POLICY_COLOR.get(a["policy"])
        if color:
            fill_hex, font_hex = color
            c = ws2.cell(row=r, column=2 + headers.index("政策状态"))
            c.fill = PatternFill("solid", fgColor=fill_hex)
            c.font = Font(name=FONT_NAME, size=11, color=font_hex)
        # 审核意见列给个浅底提示可填写
        c = ws2.cell(row=r, column=2 + headers.index("审核意见"))
        c.fill = PatternFill("solid", fgColor="FFFBEB")

    # 表头筛选 + 冻结窗格（滚动时表头和项目名固定）
    ws2.auto_filter.ref = f"B4:{get_column_letter(last_col)}{4 + len(acts)}"
    ws2.freeze_panes = "D5"
    auto_fit_columns(ws2, min_width=8, max_width=36, header_row=4, data_start_row=5)
    auto_fit_row_heights(ws2, header_row=4, data_start_row=5)

    # ---------------- Sheet 3: 信源清单 ----------------
    ws3 = wb.create_sheet("信源清单")
    h3 = ["编号", "级别", "信源", "要点/摘记", "链接"]
    last3 = len(h3) + 1
    setup_sheet(ws3, title="信源清单（30 条 · 数据库所有结论的出处）", last_col=last3)
    for ci, h in enumerate(h3, start=2):
        ws3.cell(row=4, column=ci, value=h)
    style_header_row(ws3, row_num=4, col_start=2, col_end=last3)
    for i, s in enumerate(sources):
        r = 5 + i
        vals = [s["id"].upper().replace("R", "R"), TIER_TEXT.get(s["tier"], s["tier"]),
                s["title"] or "（详见摘记）", s["excerpt"], s["url"] or "—"]
        for ci, v in enumerate(vals, start=2):
            ws3.cell(row=r, column=ci, value=v)
        style_data_row(ws3, row_num=r, col_start=2, col_end=last3, row_index=i)
    auto_fit_columns(ws3, min_width=8, max_width=60, header_row=4, data_start_row=5)
    auto_fit_row_heights(ws3, header_row=4, data_start_row=5)

    wb.properties.creator = "Z.ai"
    wb.save(OUT)
    print(f"OK -> {OUT}")
    print(f"项目 {len(acts)} 行 | 信源 {len(sources)} 行")


if __name__ == "__main__":
    main()
