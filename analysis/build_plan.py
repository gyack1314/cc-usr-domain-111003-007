"""11 月 18 日作业计划窗口推演（不认定业务有效性，只显式记录采信规则）。

输入：
  - 浏览器取证落盘的门户附件 state/evidence/browser/attachments/*.json
  - 本地材料 materials/activities.csv、zones.json、sequence.md、policy.md
输出：
  - output/activity_windows.json（按工序逐区域的窗口、依据、封锁来源、判定）
所有有效性规则写在 EVIDENCE_RULES 中并逐条落到判定理由，便于人工复核。
运行：python3 -I analysis/build_plan.py
"""
import csv
import json
from pathlib import Path

from workbench.planning import activity_windows, continuous_fit, longest_window, crew_overlap
from workbench.evidence import digest

ROOT = Path(__file__).resolve().parents[1]
PLAN_DATE = "2026-11-18"
AUTHORITY = "项目监理"  # sequence.md：停复工权限为项目监理
ATT = ROOT / "state/evidence/browser/attachments"
OUT = ROOT / "output/activity_windows.json"


def load_records():
    records = {}
    for p in sorted(ATT.glob("*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        ref = f"{r['id']}@{digest(p.read_bytes())}"
        r["_ref"] = ref
        records[r["id"]] = r
    return records


def dated(rec):
    """带 date 字段的文书必须精确匹配计划日；无 date 的复工/说明另行标记。"""
    d = rec["fields"].get("date")
    return d is None or d == PLAN_DATE


def main():
    records = load_records()
    refs = {rid: r["_ref"] for rid, r in records.items()}

    # ---- 文书有效性筛查（规则可追溯，全部基于 policy.md / sequence.md）----
    validity = {}
    for rid, r in records.items():
        f, reasons = r["fields"], []
        if not dated(r):
            reasons.append(f"date={f.get('date')} 与计划日 {PLAN_DATE} 不符")
        if f.get("issuer") != AUTHORITY:
            reasons.append(f"签发人={f.get('issuer')}，非停复工权限（{AUTHORITY}）")
        if f.get("project") != "HB-A1":
            reasons.append(f"工程编号={f.get('project')}，本项目为 HB-A1，许可不互通")
        validity[rid] = {"admissible": not reasons, "reasons": reasons,
                         "category": r["category"], "ref": r["_ref"]}

    # 复工引用链：target 必须存在；能否解除还要看权限（已在上面筛查）
    for rid, r in records.items():
        if r["category"] != "复工":
            continue
        target = r["fields"].get("target")
        if target not in records:
            validity[rid]["admissible"] = False
            validity[rid]["reasons"].append(f"引用的停工 {target} 在门户中不存在（文件链断裂）")
        else:
            validity[rid]["reasons"].append(f"引用链 {rid}→{target} 存在")

    admissible = {rid for rid, v in validity.items() if v["admissible"]}

    def pack(rid):
        f = records[rid]["fields"]
        return {"id": rid, "zones": list(f["zones"]),
                "methods": list(f.get("methods", [])),
                "start": f["start"], "end": f["end"],
                "refs": [records[rid]["_ref"]]}

    permits = [pack(rid) for rid in admissible if records[rid]["category"] == "许可"]
    suspensions = [pack(rid) for rid in admissible if records[rid]["category"] == "停工"]
    resumptions = []
    for rid in admissible:
        if records[rid]["category"] != "复工":
            continue
        item = pack(rid)
        item["target"] = records[rid]["fields"]["target"]
        resumptions.append(item)
    notes = []
    for rid in admissible:
        if records[rid]["category"] == "说明":
            f = records[rid]["fields"]
            notes.append({"id": rid, "zones": list(f["zones"]),
                          "methods": list(f.get("methods", [])),
                          "allowed": [list(x) for x in f["allowed"]],
                          "refs": [records[rid]["_ref"]], "reason": records[rid]["title"]})

    # ---- 读取班组计划 ----
    activities = []
    with (ROOT / "materials/activities.csv").open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            activities.append({
                "id": row["id"], "project": row["project"], "crew": row["crew"],
                "method": row["method"], "zones": row["zones"].split("|"),
                "plan_window": [int(row["start"]), int(row["end"])],
                "continuous_hours": int(row["continuous_hours"]),
            })

    result = {
        "plan_date": PLAN_DATE,
        "project": "HB-A1",
        "zone_names": json.loads((ROOT / "materials/zones.json").read_text(encoding="utf-8")),
        "time_convention": "半开区间 [start,end)，相邻端点不冲突；当地时间",
        "document_validity": validity,
        "excluded_documents": {rid: v for rid, v in validity.items() if not v["admissible"]},
        "activities": [],
        "open_questions": [],
    }

    for act in activities:
        method_permits = [p for p in permits if act["method"] in p["methods"]]
        method_susp = [s for s in suspensions if act["method"] in s["methods"]]
        method_res = [r for r in resumptions if act["method"] in r["methods"]]
        method_notes = [n for n in notes if act["method"] in n["methods"]]

        windows_by_zone = activity_windows(
            act["plan_window"], method_permits, method_susp, method_res, method_notes)

        zone_report = {}
        feasible_zones, partial_zones, blocked_zones = [], [], []
        for z in act["zones"]:
            info = windows_by_zone.get(z, {"windows": [], "basis": [], "blocked": [
                {"window": act["plan_window"], "refs": [], "reason": "无覆盖该区域与作业方法的有效许可"}]})
            fits = continuous_fit(info["windows"], act["continuous_hours"])
            zone_report[z] = {
                "windows": info["windows"],
                "longest_continuous_hours": longest_window(info["windows"]),
                "continuous_requirement_hours": act["continuous_hours"],
                "continuous_satisfied": fits,
                "basis": info["basis"],
                "blocked": info["blocked"],
            }
            (feasible_zones if fits else partial_zones if info["windows"] else blocked_zones).append(z)

        # 整工序判定：所有计划区域同时满足连续性才算可按原计划执行
        all_fit = all(zone_report[z]["continuous_satisfied"] for z in act["zones"])
        any_window = any(zone_report[z]["windows"] for z in act["zones"])
        if all_fit:
            verdict = "可按原计划执行"
        elif any_window:
            verdict = "部分区域/时长可行，原计划无法完整执行"
        else:
            verdict = "禁止执行（无有效窗口）"

        # 现场处置三分类：doable / blocked / needs_confirmation。
        # 算法可行不等于许可结论：跨文书拼接连续窗口、缩减区域等一律转人工确认。
        disposition_rules = []
        if act["id"] == "J1":
            disposition = "needs_confirmation"
            disposition_rules = [
                "原计划 A+B 开挖不可做：B 区被 S1 整日封锁且无有效复工（R3 签发人无权限）",
                "A 区 9-15 已由 R1 复工，可在其中安排连续 4 小时；但缩为仅 A 区属更改计划范围，"
                "须计划经理调整并经项目监理确认后方可执行",
                "B 区须等待项目监理签发、明确引用 S1 的复工通知",
            ]
        elif act["id"] == "J3":
            disposition = "needs_confirmation"
            disposition_rules = [
                "S2 停工 11-14，R2 仅解除其中 13-14；有效窗口 8-11、13-17",
                "13-17 由 R2 解除段与 P2 原许可段在端点 14 相接合并，算法上为连续 4 小时；"
                "跨文书连续性须项目监理书面确认，未确认前不得动火",
                "8-11 仅 3 小时，不满足连续 4 小时，不得用零散窗口拼接",
            ]
        elif verdict == "可按原计划执行":
            disposition = "doable"
            disposition_rules = ["许可的工程、区域、方法、时间与签发权限均匹配，窗口满足连续性要求"]
        else:
            disposition = "blocked"
            disposition_rules = ["无满足连续性要求的有效窗口"]

        result["activities"].append({
            **act, "zones": act["zones"], "zone_report": zone_report,
            "feasible_zones": feasible_zones, "partial_zones": partial_zones,
            "blocked_zones": blocked_zones, "verdict": verdict,
            "disposition": disposition, "disposition_rules": disposition_rules,
        })

    # ---- 同班组并行校验（跨工序）----
    crews = {}
    for act in result["activities"]:
        crews.setdefault(act["crew"], []).append(act)
    conflicts = []
    for crew, acts in crews.items():
        for i in range(len(acts)):
            for j in range(i + 1, len(acts)):
                wa = [w for z in acts[i]["zones"] for w in acts[i]["zone_report"][z]["windows"]]
                wb = [w for z in acts[j]["zones"] for w in acts[j]["zone_report"][z]["windows"]]
                if crew_overlap(wa, wb):
                    conflicts.append({"crew": crew, "activities": [acts[i]["id"], acts[j]["id"]],
                                      "note": "窗口相交，排班时必须错开，不得同时两处施工"})
    result["crew_conflicts"] = conflicts

    # ---- 待询问题（缺证/需审批人员确认）----
    result["open_questions"] = [
        {"id": "Q1", "about": "J3 焊接二 动火",
         "question": "R2 仅解除 S2 的 13-14 段，B 区动火有效窗口为 8-11 与 13-17；13-17 由 R2 解除段(13-14)"
                     "与 P2 原许可段(14-17)在端点 14 相接合并而成。算法上满足连续 4 小时，但是否认可"
                     "跨文书（复工通知+原许可）的连续动火，须项目监理书面确认；不确认则 J3 明日无法连续 4 小时。",
         "refs": [refs["P2"], refs["S2"], refs["R2"]]},
        {"id": "Q2", "about": "J1 土建一 开挖",
         "question": "R1 只解除 S1 的 A 区 9-15；B 区开挖整日停工，R3 为班组长签发、无权限解除 S1。"
                     "若拟将 J1 缩为仅 A 区开挖（9-15 内安排连续 4 小时），属更改作业计划范围，"
                     "须计划经理调整并经项目监理确认；B 区复工须等待项目监理签发、明确引用 S1 的复工通知。",
         "refs": [refs["S1"], refs["R1"], refs["R3"]]},
        {"id": "Q3", "about": "NOTE 适用日期",
         "question": "C 区噪声时间限制（NOTE）无 date 字段，按常驻限制适用于 11-18 并已据此约束 J2；"
                     "请项目监理确认该限制在计划日仍然有效。",
         "refs": [refs["NOTE"]]},
    ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(OUT),
                      "activities": [(a["id"], a["verdict"]) for a in result["activities"]],
                      "excluded": sorted(result["excluded_documents"])}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
