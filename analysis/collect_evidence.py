"""通过 Chromium 从本地门户页面读取文书并保存附件。

仅做取证：遍历资料目录、逐条打开记录页、下载 JSON 附件与文书副本、
比对页面渲染的编号@摘要与下载字节的 SHA-256 是否一致。不做业务认定。
运行：python3 -I analysis/collect_evidence.py
"""
import hashlib
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8765"
IDS = ["P1", "P2", "S1", "R1", "S2", "R2", "P9", "R3", "NOTE"]
OUT = Path(__file__).resolve().parents[1] / "state/evidence/browser"
ATT = OUT / "attachments"
DOC = OUT / "documents"
SHOTS = OUT / "screenshots"


def main():
    for d in (ATT, DOC, SHOTS):
        d.mkdir(parents=True, exist_ok=True)
    report = {"base": BASE, "records": [], "checks": []}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1280, "height": 900}, accept_downloads=True)
        page = ctx.new_page()

        # 目录页：确认门户可检索、分页存在
        page.goto(BASE + "/", wait_until="domcontentloaded")
        report["index_title"] = page.title()
        report["index_count_text"] = page.get_by_test_id("count").inner_text()
        page.screenshot(path=str(SHOTS / "index.png"), full_page=True)

        for rid in IDS:
            page.goto(f"{BASE}/record/{rid}", wait_until="domcontentloaded")
            title = page.title()
            shown_id = page.get_by_test_id("record-id").inner_text()
            shown_ref = page.get_by_test_id("reference").inner_text()
            fields_text = page.get_by_test_id("fields").inner_text()
            page.screenshot(path=str(SHOTS / f"{rid}.png"), full_page=True)

            # 下载原始材料（JSON 附件）
            with page.expect_download() as ev:
                page.get_by_role("link", name="下载原始材料").click()
            att_path = ATT / f"{rid}.json"
            ev.value.save_as(str(att_path))
            att_bytes = att_path.read_bytes()
            att_digest = hashlib.sha256(att_bytes).hexdigest()
            att_record = json.loads(att_bytes)

            # 下载文书/扫描副本（门户返回 .txt 或 .svg）
            with page.expect_download() as ev2:
                page.get_by_role("link", name="下载文书或扫描副本").click()
            doc_name = ev2.value.suggested_filename
            doc_path = DOC / doc_name
            ev2.value.save_as(str(doc_path))
            doc_digest = hashlib.sha256(doc_path.read_bytes()).hexdigest()

            ref_ok = shown_ref == f"{rid}@{att_digest}"
            id_ok = shown_id == rid == att_record["id"]
            report["checks"].append({"id": rid, "reference_matches_attachment": ref_ok, "id_consistent": id_ok})
            report["records"].append(
                {
                    "id": rid,
                    "page_title": title,
                    "shown_reference": shown_ref,
                    "attachment_sha256": att_digest,
                    "attachment_file": att_path.name,
                    "document_file": doc_name,
                    "document_sha256": doc_digest,
                    "category": att_record["category"],
                    "title_field": att_record["title"],
                    "revision": att_record["revision"],
                    "fields": att_record["fields"],
                    "fields_rendered_on_page": fields_text,
                }
            )
        browser.close()

    report["all_checks_passed"] = all(c["reference_matches_attachment"] and c["id_consistent"] for c in report["checks"])
    out_json = OUT / "portal_reading.json"
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out_json), "all_checks_passed": report["all_checks_passed"], "records": len(report["records"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
