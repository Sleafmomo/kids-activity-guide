#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成网页专用数据 web/data.js。

关键职责：**个性化内容物理隔离**——detail_original（原定制清单推荐理由，含针对特定孩子的措辞）
与 source_original 不进入网页数据；网页只拿到全年龄客观字段。
重跑：python3 scripts/build_web_data.py
"""
import json
import os

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
WEB = os.path.join(BASE, "web")

# 网页数据中剔除的字段（个性化/维护用；age_check 为内部质检字段，网页已不展示）
DROP_FIELDS = {"detail_original", "source_original", "badge_original", "verified_at", "notes", "age_check"}


def main():
    with open(os.path.join(BASE, "data", "activities.json"), encoding="utf-8") as f:
        activities = json.load(f)["activities"]
    with open(os.path.join(BASE, "data", "categories.json"), encoding="utf-8") as f:
        categories = json.load(f)
    with open(os.path.join(BASE, "data", "abilities.json"), encoding="utf-8") as f:
        abilities = json.load(f)
    with open(os.path.join(BASE, "data", "sources.json"), encoding="utf-8") as f:
        sources = json.load(f)
    with open(os.path.join(BASE, "data", "policies.json"), encoding="utf-8") as f:
        policies = json.load(f)
    with open(os.path.join(BASE, "data", "guides.json"), encoding="utf-8") as f:
        guides = json.load(f)

    version = json.load(open(os.path.join(BASE, "data", "activities.json"), encoding="utf-8"))["meta"]["version"]

    clean = []
    for a in activities:
        item = {k: v for k, v in a.items() if k not in DROP_FIELDS}
        # 别名是搜索用的内部字段，网页端已用不到（搜索直接对 name+aliases 在前端做）→ 保留
        clean.append(item)

    data = {
        "meta": {
            "version": version,
            "generated_at": "2026-10-31",
            "count": len(clean),
            "disclaimer": "本工具信息仅供参考，报班前请实地核实机构资质；政策类结论以官方最新发布为准。",
        },
        "categories": categories,
        "abilities": abilities,
        "sources": sources,
        "policies": policies,
        "guides": guides,
        "activities": clean,
    }

    os.makedirs(WEB, exist_ok=True)
    out = os.path.join(WEB, "data.js")
    with open(out, "w", encoding="utf-8") as f:
        f.write("// 由 scripts/build_web_data.py 自动生成，请勿手改；数据源：data/*.json\n")
        f.write("const DATA = ")
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")

    # 微信小程序版数据（同一份，模块导出）
    MINIAPP = os.path.join(BASE, "miniapp")
    os.makedirs(MINIAPP, exist_ok=True)
    out2 = os.path.join(MINIAPP, "data.js")
    with open(out2, "w", encoding="utf-8") as f:
        f.write("// 由 scripts/build_web_data.py 自动生成，请勿手改；数据源：data/*.json\n")
        f.write("module.exports = ")
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")

    # 隐私自检：确认个性化字段未进入网页数据
    blob = json.dumps(clean, ensure_ascii=False)
    for kw in ["孩子已4岁半", "4岁5个月", "他未表现", "本城", "本区", "家庭决策排除", "我家"]:
        assert kw not in blob, f"个性化关键词泄漏到网页数据: {kw}"
    print(f"OK -> {out} + miniapp/data.js  ({len(clean)} 项, 个性化字段已隔离)")


if __name__ == "__main__":
    main()
