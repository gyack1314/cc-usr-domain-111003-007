import unittest
from workbench.planning import (
    merge_adjacent, apply_suspension, apply_resumption,
    activity_windows, continuous_fit, crew_overlap,
)


class PlanningTests(unittest.TestCase):
    def test_merge_adjacent_keeps_gaps(self):
        # 端点相接才合并；有间隔的零散窗口不得冒充连续
        self.assertEqual(merge_adjacent([[8, 11], [11, 14]]), [[8, 14]])
        self.assertEqual(merge_adjacent([[8, 10], [14, 17]]), [[8, 10], [14, 17]])
        self.assertEqual(merge_adjacent([[13, 14], [14, 17]]), [[13, 17]])

    def test_suspension_and_partial_resumption(self):
        # S1: A/B 开挖 8-17 停工；R1 仅解除 A 区 9-15
        permits = [{"id": "P1", "zones": ["A", "B"], "start": 8, "end": 17, "refs": ["P1"]}]
        susp = [{"id": "S1", "zones": ["A", "B"], "start": 8, "end": 17, "refs": ["S1"]}]
        res = [{"target": "S1", "zones": ["A"], "start": 9, "end": 15, "refs": ["R1"]}]
        out = activity_windows([8, 17], permits, susp, res, [])
        self.assertEqual(out["A"]["windows"], [[9, 15]])
        self.assertEqual(out["B"]["windows"], [])
        self.assertEqual(out["B"]["blocked"][0]["window"], [8, 17])

    def test_resumption_cannot_extend_beyond_suspension(self):
        permits = [{"id": "P1", "zones": ["B"], "start": 8, "end": 17, "refs": ["P1"]}]
        susp = [{"id": "S2", "zones": ["B"], "start": 11, "end": 14, "refs": ["S2"]}]
        # 复工区间大于停工区间，解除量仍被夹在 11-14 内
        res = [{"target": "S2", "zones": ["B"], "start": 9, "end": 16, "refs": ["R2"]}]
        out = activity_windows([8, 17], permits, susp, res, [])
        self.assertEqual(out["B"]["windows"], [[8, 17]])

    def test_hotwork_adjacent_pieces_merge_but_gapped_do_not(self):
        # P2 8-17；S2 11-14；R2 只解除 13-14 → 8-11 与 13-17 在 14 处相接
        permits = [{"id": "P2", "zones": ["B"], "start": 8, "end": 17, "refs": ["P2"]}]
        susp = [{"id": "S2", "zones": ["B"], "start": 11, "end": 14, "refs": ["S2"]}]
        res = [{"target": "S2", "zones": ["B"], "start": 13, "end": 14, "refs": ["R2"]}]
        out = activity_windows([8, 17], permits, susp, res, [])
        self.assertEqual(out["B"]["windows"], [[8, 11], [13, 17]])
        # 13-17 为端点相接合并出的单段 4 小时窗口；5 小时无处可放
        self.assertTrue(continuous_fit(out["B"]["windows"], 4))
        self.assertFalse(continuous_fit(out["B"]["windows"], 5))
        # 若复工缺位、只剩 8-11 一段，则 4 小时连续工序无法满足
        self.assertFalse(continuous_fit([[8, 11]], 4))
        # 若两段在 11 处相接（13 点解除改成 11 点解除）则可合并成 4 小时
        res2 = [{"target": "S2", "zones": ["B"], "start": 11, "end": 14, "refs": ["Rx"]}]
        out2 = activity_windows([8, 17], permits, susp, res2, [])
        self.assertEqual(out2["B"]["windows"], [[8, 17]])
        self.assertTrue(continuous_fit(out2["B"]["windows"], 4))

    def test_note_time_restriction(self):
        permits = [{"id": "P1", "zones": ["C"], "start": 8, "end": 17, "refs": ["P1"]}]
        notes = [{"id": "NOTE", "zones": ["C"], "allowed": [[10, 12], [14, 16]],
                  "refs": ["NOTE"], "reason": "C区噪声时间限制"}]
        out = activity_windows([10, 14], permits, [], [], notes)
        # 计划只到 14：下午窗口 14-16 与 [10,14) 无正长度交集，仅剩 10-12
        self.assertEqual(out["C"]["windows"], [[10, 12]])
        out_full = activity_windows([8, 17], permits, [], [], notes)
        self.assertEqual(out_full["C"]["windows"], [[10, 12], [14, 16]])

    def test_crew_overlap_boundary(self):
        self.assertFalse(crew_overlap([[9, 12]], [[12, 15]]))  # 相邻端点不冲突
        self.assertTrue(crew_overlap([[9, 12]], [[11, 15]]))
        self.assertFalse(crew_overlap([[9, 11]], [[13, 15]]))


if __name__ == "__main__":
    unittest.main()
