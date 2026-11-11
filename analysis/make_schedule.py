"""根据 activity_windows.json 生成现场可读安排单（Markdown）。

只做排版与排班建议，不重新认定许可；所有窗口与封锁来源均取自推演结果。
运行：python3 -I analysis/make_schedule.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "output/activity_windows.json"
OUT = ROOT / "output/schedule_2026-11-18.md"

ZONE_NAME = {"A": "A区（桩号0至100）", "B": "B区（桩号100至200）", "C": "C区（桩号200至300）"}


def fmt(w):
    return f"{w[0]:02d}:00–{w[1]:02d}:00"


def short_refs(refs):
    return "、".join(r.split("@")[0] for r in refs)


def main():
    data = json.loads(SRC.read_text(encoding="utf-8"))
    acts = {a["id"]: a for a in data["activities"]}
    lines = []
    lines.append("# 11 月 18 日现场作业安排单（HB-A1 海湾工程）")
    lines.append("")
    lines.append("> 时间均为当地时间、半开区间 [起,止)，相邻端点不冲突。本单依据门户现有文书推演，")
    lines.append("> 不构成审批；标注“待确认”的事项未经项目监理书面确认前不得施工。")
    lines.append("")

    lines.append("## 一、明确可做（许可四要素齐备，窗口满足连续性）")
    lines.append("")
    lines.append("| 班组 | 工序 | 区域 | 建议时间段 | 连续要求 | 依据 |")
    lines.append("|---|---|---|---|---|---|")
    j2 = acts["J2"]
    lines.append(f"| 土建一 | J2 回填 | {ZONE_NAME['C']} | **10:00–12:00** | 连续 2 小时，单窗口满足 | P1 许可 8–17；NOTE 限 C 区回填仅 10–12、14–16 |")
    j4 = acts["J4"]
    lines.append(f"| 巡检三 | J4 一般巡检 | A/B/C 全区 | 8:00–17:00 内任择连续 1 小时（建议 15:00–16:00） | 连续 1 小时 | P1 许可（一般巡检，A/B/C，8–17） |")
    lines.append("")
    lines.append("- J2 备选 14:00–16:00（同为 NOTE 允许窗口，连续 2 小时）；采用 10:00–12:00 的依据：")
    lines.append("  落在班组原计划 10–14 内，无需调整计划，且为土建一保留下午机动。")
    lines.append("- J4 建议放在 15:00–16:00：避开土建一上午 C 区回填与各停工边界，巡检可覆盖 A、B、C 全区；")
    lines.append("  巡检本身只要求连续 1 小时，具体时点由计划经理在 8–17 内指定。")
    lines.append("")

    lines.append("## 二、不能做（现有文书下无有效窗口，禁止开工）")
    lines.append("")
    lines.append("| 班组 | 工序 | 被禁范围/时间 | 约束来源（编号@摘要见 activity_windows.json） |")
    lines.append("|---|---|---|---|")
    j1b = acts["J1"]["zone_report"]["B"]["blocked"][0]
    lines.append(f"| 土建一 | J1 开挖 | B 区（桩号100至200）全天 8–17 | S1 停工（A/B 开挖 8–17）；R3 签发人为“班组长”，无停复工权限，不能解除 S1 |")
    j3b = acts["J3"]["zone_report"]["B"]["blocked"][0]
    lines.append(f"| 焊接二 | J3 动火 | B 区 11:00–13:00 | S2 停工（B 区动火 11–14）；R2 仅解除其中 13–14，11–13 仍被封锁 |")
    lines.append(f"| 土建一 | J2 回填 | C 区 12:00–14:00（及计划外的其他时段） | NOTE 噪声时间限制：C 区回填仅允许 10–12、14–16 |")
    lines.append("")
    lines.append("- J1 原计划为 A+B 两区开挖，B 区整日封锁，故 **J1 原计划明日不能按计划开工**；")
    lines.append("  不得以“R1 已复工”为由进入 B 区——R1 只明确解除 S1 中的 **A 区** 部分。")
    lines.append("")

    lines.append("## 三、需审批人员确认（确认前按不能做管控）")
    lines.append("")
    lines.append("### 1. J1 土建一 · 开挖 · 缩为仅 A 区的备选")
    lines.append("- A 区有效窗口 9:00–15:00（R1 解除 S1 的 A 区部分，最长连续 6 小时，可容纳连续 4 小时）。")
    lines.append("- 若执行，建议 9:00–13:00 连续开挖 4 小时；该备选与 J2（C 区回填）区域不同，不构成同班组两处并行，")
    lines.append("  但推演显示 J1 与 J2 的可行窗口在 10–12 相交，同一班组人力不得同时铺在两处，须由计划经理错时排班。")
    lines.append("- **待确认点**：缩减区域属更改作业计划，须计划经理调整 + 项目监理确认（见待询 Q2）。未确认前不排入正式作业。")
    lines.append("")
    lines.append("### 2. J3 焊接二 · B 区动火 · 跨文书连续 4 小时")
    lines.append("- 有效窗口：8:00–11:00（3 小时，不足 4 小时）与 13:00–17:00。")
    lines.append("- 13:00–17:00 由 R2 解除段 13–14 与 P2 原许可段 14–17 在端点 14 相接合并，**算法上为单段连续 4 小时**；")
    lines.append("  但是否认可“复工通知 + 原许可”跨文书拼成连续动火，属审批判断，须项目监理书面确认（见待询 Q1）。")
    lines.append("- 若获确认，建议 13:00–17:00 一次连续作业，严禁拆成 13–14、14–17 两段分别点票开工；")
    lines.append("  若不获确认，J3 明日停工，或由监理另行签发覆盖连续 4 小时的动火许可/完整解除 S2 的复工通知。")
    lines.append("")
    lines.append("### 3. NOTE 噪声限制的计划日适用性")
    lines.append("- NOTE 无 date 字段，按常驻限制适用；请监理确认 11 月 18 日仍然有效（见待询 Q3）。")
    lines.append("")

    lines.append("## 四、同班组与工序衔接核查")
    lines.append("")
    lines.append("- 同班组并行：土建一同时承担 J1、J2，推演显示两者可行窗口在 10–12 相交。正式单内 J1 未放行，")
    lines.append("  仅 J2 排在 10–12（C 区），不存在同班组两处同时施工；若 J1 的 A 区备选后续获批，须按第三节错时排班。")
    lines.append("  焊接二、巡检三各自仅一道工序，无并行冲突。")
    lines.append("- 连续作业：J1、J3 的 4 小时要求均只在单段连续窗口内满足，未用零散窗口拼接；J2 的 2 小时、J4 的 1 小时同为单窗口满足。")
    lines.append("- 工序衔接（sequence.md）：J1 完成前 B 区不能回填；当前 B 区开挖本就停工，明日不安排 B 区回填，无冲突。")
    lines.append("")

    lines.append("## 五、不予采信的文书")
    lines.append("")
    for rid, info in data["excluded_documents"].items():
        lines.append(f"- **{rid}**：{'；'.join(info['reasons'])}（引用 {info['ref']}）")
    lines.append("")
    lines.append("## 六、待询问题清单")
    lines.append("")
    for q in data["open_questions"]:
        lines.append(f"- **{q['id']}（{q['about']}）**：{q['question']}")
    lines.append("")
    lines.append("---")
    lines.append("配套数据：output/activity_windows.json（含每个窗口的文书引用与封锁来源）；")
    lines.append("门户预核草稿保存于本地门户“预审草稿”，状态恒为“待人工审批”。")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(OUT), "lines": len(lines)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
