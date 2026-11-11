"""分区停复工下的作业窗口演算（纯函数，不做审批认定）。

所有时间沿用业务规程：当地时间半开区间 [start, end)，相邻端点不冲突。
本模块只对显式传入的记录做集合与时间运算；一份复工是否"有权"、
一份文书是否适用于目标日期，由调用方按 materials/policy.md 判定后传入。
"""
from .domain import intersect, subtract, zone_overlap


def merge_adjacent(windows):
    """合并仅在端点相接（半开区间下无缝）的窗口；有间隔的不合并。"""
    ordered = sorted((list(w) for w in windows), key=lambda w: (w[0], w[1]))
    merged = []
    for w in ordered:
        if merged and w[0] == merged[-1][1]:
            merged[-1][1] = w[1]
        else:
            merged.append(list(w))
    return merged


def apply_suspension(open_windows, block):
    """从已开放窗口中扣除一个停工区间。"""
    result = []
    for w in open_windows:
        result.extend(subtract(w, [block]))
    return merge_adjacent(result)


def apply_resumption(blocked_windows, base_suspension, resumption):
    """复工只解除其明确引用的停工中、与复工区间相交的部分。

    返回 (解除后仍被封锁的窗口, 本次复工实际解除的窗口)。
    解除范围同时受复工自身时间与原停工时间约束，不得扩大原停工之外。
    """
    lifted = intersect(base_suspension, resumption)
    if lifted is None:
        return list(blocked_windows), []
    still = []
    for w in blocked_windows:
        still.extend(subtract(w, [lifted]))
    return merge_adjacent(still), [lifted]


def activity_windows(plan_window, permits, suspensions, resumptions, notes):
    """计算单项作业（固定工程+作业方法）在各区域的可作业窗口。

    permits/suspensions/resumptions/notes 均为已通过工程、方法、日期、
    签发权限筛选的 dict，含 zones 与时间窗口字段。复工 dict 须含
    target（所引用停工的调用方编号）。
    返回 {zone: {"windows": [...], "basis": [{window, refs, kind}],
                 "blocked": [{"window", "refs", "reason"}]}}。
    """
    # 1) 许可交集：必须有一份同时覆盖该区域与方法、且时间相交的许可
    result = {}
    zones = sorted({z for p in permits for z in p["zones"]})
    for zone in zones:
        basis, open_windows, blocked = [], [], []
        zone_permits = [p for p in permits if zone in p["zones"]]
        for p in zone_permits:
            w = intersect(plan_window, [p["start"], p["end"]])
            if w is not None:
                open_windows.append(w)
                basis.append({"window": w, "refs": list(p["refs"]), "kind": "许可"})
        if not open_windows:
            result[zone] = {"windows": [], "basis": [], "blocked": [
                {"window": list(plan_window), "refs": [], "reason": "无覆盖该区域与作业方法的有效许可"}]}
            continue
        open_windows = merge_adjacent(open_windows)

        # 2) 停工（仅保留覆盖本区域的）
        live_blocks = []
        for s in suspensions:
            if zone not in s["zones"]:
                continue
            sw = intersect(plan_window, [s["start"], s["end"]])
            if sw is None:
                continue
            open_windows = apply_suspension(open_windows, sw)
            live_blocks.append({"id": s["id"], "window": sw, "refs": list(s["refs"])})

        # 3) 复工：只能削弱其 target 停工，且范围不超过原停工
        for r in resumptions:
            if zone not in r["zones"]:
                continue
            target = next((b for b in live_blocks if b["id"] == r["target"]), None)
            if target is None:
                continue
            rw = intersect(plan_window, [r["start"], r["end"]])
            if rw is None:
                continue
            still, lifted = apply_resumption(
                [target["window"]], target["window"], rw
            )
            if not lifted:
                continue
            # 原封锁块被解除部分从封锁清单中移除/缩小
            target["window"] = still[0] if still else None
            for lw in lifted:
                # 解除段重新并入开放窗口，再做合并
                open_windows = merge_adjacent(open_windows + [lw])
                basis.append({"window": lw, "refs": list(r["refs"]), "kind": "复工解除"})

        for b in live_blocks:
            if b["window"] is not None:
                blocked.append({"window": b["window"], "refs": b["refs"],
                                "reason": "停工未被有效复工解除"})

        # 4) 说明类限制（如噪声窗口）：只允许出现在 allowed 内
        for n in notes:
            if zone not in n["zones"]:
                continue
            allowed = merge_adjacent(
                [w for pair in n["allowed"] if (w := intersect(plan_window, pair)) is not None]
            )
            restricted = []
            kept = []
            for w in open_windows:
                pieces = [seg for seg in (intersect(w, a) for a in allowed) if seg is not None]
                kept.extend(pieces)
                for cut in subtract(w, allowed):
                    restricted.append(cut)
            open_windows = merge_adjacent(kept)
            for cut in restricted:
                blocked.append({"window": cut, "refs": list(n["refs"]),
                                "reason": n.get("reason", "说明类时间限制")})

        result[zone] = {"windows": open_windows, "basis": basis,
                        "blocked": sorted(blocked, key=lambda b: b["window"][0])}
    return result


def continuous_fit(windows, hours):
    """是否存在单个连续窗口满足连续作业时长；禁止拼接有间隔的窗口。"""
    return any((w[1] - w[0]) >= hours for w in windows)


def longest_window(windows):
    return max((w[1] - w[0] for w in windows), default=0)


def crew_overlap(windows_a, windows_b):
    """同一班组两处作业的时间是否相交；半开相邻端点不算冲突。"""
    for a in windows_a:
        for b in windows_b:
            if intersect(a, b) is not None:
                return True
    return False
