#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 data/*.json 的完整性与一致性，并输出数据质量报告。"""
import json
import os
import sys

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

def load(name):
    with open(os.path.join(BASE, name), encoding="utf-8") as f:
        return json.load(f)

def main():
    acts = load("activities.json")["activities"]
    sources = load("sources.json")
    cats = load("categories.json")
    abilities = load("abilities.json")
    policies = load("policies.json")

    errors, warns = [], []
    cat_ids = {c["id"] for c in cats}
    ab_ids = {a["id"] for a in abilities}
    src_ids = {s["id"] for s in sources}
    pol_ids = {p["id"] for p in policies}
    valid_traits = {"indoor": {"indoor", "outdoor", "both"},
                    "group": {"team", "solo", "both"},
                    "tempo": {"active", "calm", "both"},
                    "cost": {"low", "mid", "high"}}
    valid_policy = {"normal", "caution", "discouraged", "banned_preschool",
                    "pseudoscience", "encouraged", "redline"}

    seen_names = {}
    for a in acts:
        aid = a["id"]
        if a["category"] not in cat_ids:
            errors.append(f"{aid}: 非法 category {a['category']}")
        for ab in a["abilities"]:
            if ab not in ab_ids:
                errors.append(f"{aid}: 非法 ability {ab}")
        if not a["abilities"] and a["policy"] in ("normal", "caution", "encouraged"):
            errors.append(f"{aid}: 无能力标签")
        for k, allowed in valid_traits.items():
            if a["traits"].get(k) not in allowed:
                errors.append(f"{aid}: traits.{k}={a['traits'].get(k)!r} 非法")
        if a["policy"] not in valid_policy:
            errors.append(f"{aid}: 非法 policy {a['policy']}")
        if a.get("heat") not in {"hot", "warm", "cool", "rare"}:
            errors.append(f"{aid}: 非法/缺失 heat {a.get('heat')!r}")
        if not (a.get("detail") or "").strip():
            errors.append(f"{aid}: 缺项目介绍 detail")
        ac = a.get("age_check")
        if ac is not None and (ac.get("level") != "verified" or not ac.get("sources")):
            errors.append(f"{aid}: age_check 结构非法")
        for r in a["source_refs"]:
            if r not in src_ids:
                errors.append(f"{aid}: 引用不存在的信源 {r}")
        for p in a["official_support"]:
            if p not in pol_ids:
                errors.append(f"{aid}: 引用不存在的政策文件 {p}")
        if a["policy"] == "encouraged" and not a["official_support"]:
            errors.append(f"{aid}: 标记 encouraged 但无官方文件支持")
        if a["status"] not in ("active", "excluded"):
            errors.append(f"{aid}: 非法 status {a['status']}")
        key = "".join(a["name"].split())
        if key in seen_names:
            errors.append(f"疑似重复: {a['name']} 与 {seen_names[key]}")
        seen_names[key] = a["name"]
        # 有 caution 的建议有信源
        if a["caution"] and not a["source_refs"] and a["policy"] == "normal":
            warns.append(f"{aid}: 有 caution 但无信源引用")
        # 年龄逻辑
        if a["age_start"] is not None and a["age_stop"] is not None \
           and a["age_stop"] < a["age_start"]:
            errors.append(f"{aid}: age_stop < age_start")

    # 年龄覆盖统计（3-12 岁每个半岁档有多少项目适龄）
    coverage = {}
    for age in [3, 3.5, 4, 4.5, 5, 5.5, 6, 7, 8, 9, 10, 11, 12]:
        n = sum(1 for a in acts
                if a["status"] == "active"
                and a["age_start"] is not None and a["age_start"] <= age
                and (a["age_stop"] is None or age <= a["age_stop"]))
        coverage[age] = n

    # 能力标签覆盖
    ab_count = {a["id"]: 0 for a in abilities}
    for act in acts:
        for ab, w in act["abilities"].items():
            ab_count[ab] += w  # 加权：主=2 次=1

    print(f"项目 {len(acts)} 项 | 信源 {len(sources)} 条 | 政策文件 {len(policies)} 份 | 分类 {len(cats)} | 能力 {len(abilities)}")
    print("\n各年龄适龄项目数（active）:")
    print("  " + "  ".join(f"{k}岁:{v}" for k, v in coverage.items()))
    print("\n能力标签加权覆盖（主=2/次=1）:")
    for a in abilities:
        print(f"  {a['name']:<4} {ab_count[a['id']]}")
    if warns:
        print("\n警告:")
        for w in warns:
            print("  ~", w)
    if errors:
        print("\n错误:")
        for e in errors:
            print("  !", e)
        sys.exit(1)
    print("\n校验通过 ✓")

if __name__ == "__main__":
    main()
