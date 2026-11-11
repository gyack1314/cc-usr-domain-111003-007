"""通过浏览器在本地门户保存 11-18 作业窗口预核草稿。

草稿只做预审，门户不提供审批接口，保存后状态恒为“待人工审批”。
引用全部 9 份门户资料的 编号@SHA256（取自浏览器取证的 portal_reading.json），
正文逐段摘录门户原文，不改动任何许可事实。
运行：python3 -I analysis/save_draft.py
"""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

BASE = "http://127.0.0.1:8765"
ROOT = Path(__file__).resolve().parents[1]
READING = ROOT / "state/evidence/browser/portal_reading.json"
DRAFT_KEY = "precheck-2026-11-18-windows"
SHOT = ROOT / "state/evidence/browser/screenshots/draft_saved.png"

BODY = """一、预核范围与依据
计划日 2026-11-18，工程 HB-A1（海湾工程），分区 A=桩号0至100、B=桩号100至200、C=桩号200至300。
时间为当地时间半开区间 [start,end)，相邻端点不冲突。本草稿依据门户现行 9 份资料（P1、P2、S1、R1、S2、R2、P9、R3、NOTE）的页面原文与附件摘要推演，不构成审批。

二、门户原文摘录（关键字段）
1. P1 A1一般工程许可：project=HB-A1，zones=[A,B,C]，methods=[开挖,回填,一般巡检]，date=2026-11-18，8-17，issuer=项目监理。
2. P2 B区动火许可：project=HB-A1，zones=[B]，methods=[动火]，date=2026-11-18，8-17，issuer=项目监理。
3. S1 AB开挖停工：project=HB-A1，zones=[A,B]，methods=[开挖]，date=2026-11-18，8-17，issuer=项目监理。
4. R1 A区部分复工：target=S1，zones=[A]，methods=[开挖]，9-15，issuer=项目监理。仅解除 S1 的 A 区部分。
5. S2 B区动火暂停：zones=[B]，methods=[动火]，11-14，date=2026-11-18，issuer=项目监理。
6. R2 B区下午动火：target=S2，zones=[B]，methods=[动火]，13-14，issuer=项目监理。仅解除 S2 的 13-14 段。
7. P9 同名A2工程许可：project=HB-A2，zones=[B]，methods=[开挖]，8-17。工程编号不符，对 HB-A1 不产生许可。
8. R3 施工队口头复工纪要：target=S1，zones=[B]，methods=[开挖]，8-17，issuer=班组长。签发权限不符，不能解除 S1。
9. NOTE C区噪声时间限制：zones=[C]，methods=[回填]，allowed=[10,12],[14,16]，issuer=项目监理；无 date 字段。

三、逐工序预核结论（算法结论，不替代审批）
J1 土建一 开挖（A|B，计划8-16，连续4h）：A 区窗口 9-15（R1 解除，最长连续6h）；B 区 8-17 被 S1 整日封锁，R3 无权解除。原计划 A+B 不可按计划执行；缩为仅 A 区属计划变更，须计划经理调整并经项目监理确认。
J2 土建一 回填（C，计划10-14，连续2h）：NOTE 限制下窗口仅 10-12（计划内）与 14-16（计划外备选）；建议 10-12 一次连续完成。许可 P1 覆盖。
J3 焊接二 动火（B，8-17，连续4h）：S2 停工 11-14，R2 仅解除 13-14；有效窗口 8-11（3h，不足）与 13-17。13-17 由 R2 解除段 13-14 与 P2 原许可段 14-17 在端点 14 相接合并，算法上连续 4h；跨文书连续性须项目监理书面确认，未确认前不得动火，禁止拆段点票。
J4 巡检三 一般巡检（A|B|C，8-17，连续1h）：P1 全区许可，8-17 内任择连续 1 小时，建议 15-16。

四、同班组与衔接
土建一 J1/J2 可行窗口 10-12 相交，同一班组不得两处同时施工，须错时；J1 完成前 B 区不得回填，明日 B 区本就停工，无冲突。

五、待询问题
Q1：项目监理是否认可 R2+P2 跨文书组成的 13-17 连续动火窗口（否则 J3 明日停工或另签完整解除/许可）。
Q2：是否批准 J1 缩为仅 A 区开挖（9-15 内连续 4h，建议 9-13）；B 区复工等待项目监理明确引用 S1 的复工通知。
Q3：NOTE 无日期，确认其 C 区噪声限制在 2026-11-18 仍有效。

六、不予采信
P9（工程编号 HB-A2，许可不互通）；R3（班组长签发，无停复工权限）。

本草稿为预审材料，状态：待人工审批；不构成签章、发布、预约或对外通知。
"""


def main():
    reading = json.loads(READING.read_text(encoding="utf-8"))
    refs = [r["shown_reference"] for r in reading["records"]]
    assert len(refs) == 9 and len(set(refs)) == 9

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1280, "height": 1400})
        page.goto(BASE + "/draft/new", wait_until="domcontentloaded")
        page.get_by_label("草稿编号").fill(DRAFT_KEY)
        page.get_by_label("标题", exact=True).fill("2026-11-18 作业许可窗口预核（HB-A1）")
        page.get_by_label("正文", exact=True).fill(BODY)
        page.get_by_label("资料引用，每行一项 编号@摘要").fill("\n".join(refs))
        page.get_by_role("button", name="保存预审草稿").click()
        expect(page).to_have_url(BASE + "/draft/" + DRAFT_KEY)
        expect(page.get_by_test_id("draft-status")).to_have_text("待人工审批")
        # 回读校验正文与引用
        expect(page.get_by_label("正文", exact=True)).to_have_value(BODY)
        page.screenshot(path=str(SHOT), full_page=True)
        status = page.get_by_test_id("draft-status").inner_text()
        title = page.title()
        browser.close()

    print(json.dumps({"draft_key": DRAFT_KEY, "status": status, "title": title,
                      "refs": refs, "screenshot": str(SHOT)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
