#!/usr/bin/env python3
"""Read-only DOCX ZIP/XML structure inventory; not an academic or layout validator."""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
MAX_PART = 32 * 1024 * 1024
MAX_TOTAL = 128 * 1024 * 1024
MAX_ENTRIES = 4096
CANDIDATE = re.compile(r"指导[教老]师意见|导师意见|学院.*意见|签名|签字|盖章|审批|审核意见")


def parse_xml(blob: bytes, name: str) -> ET.Element:
    # ElementTree expands internal entities: reject DTDs before parsing untrusted files.
    # OOXML is XML UTF-8/UTF-16; reject embedded NUL as well to prevent UTF-16 bypass.
    if b"\x00" in blob or re.search(br"<!\s*(?:DOCTYPE|ENTITY)\b", blob, re.I):
        raise ValueError(f"{name}: 不支持DTD、实体声明或含NUL的XML；停止检查")
    try:
        return ET.fromstring(blob)
    except ET.ParseError as exc:
        raise ValueError(f"{name}: XML解析失败: {exc}") from exc


def inspect(path: Path, show_text: bool = False) -> dict:
    if path.suffix.lower() != ".docx":
        raise ValueError("仅支持.docx；.doc/.dotx需先用适当工具处理，不能改扩展名代替转换")
    if not path.is_file():
        raise ValueError("输入文件不存在或不是普通文件")
    try:
        with zipfile.ZipFile(path) as z:
            infos = z.infolist()
            if len(infos) > MAX_ENTRIES or sum(x.file_size for x in infos) > MAX_TOTAL:
                raise ValueError("压缩包条目或展开总量超出安全上限")
            names = [x.filename for x in infos]
            if len(names) != len(set(names)):
                raise ValueError("压缩包存在重复条目，无法可靠确定文件内容")
            need = ("[Content_Types].xml", "_rels/.rels", "word/document.xml")
            for name in need:
                if name not in names:
                    raise ValueError(f"缺少必要部件：{name}")
                info = z.getinfo(name)
                if info.file_size > MAX_PART or info.flag_bits & 1:
                    raise ValueError(f"部件过大或已加密：{name}")
            # Checksums are checked when the selected entries are read; do not decompress every entry.
            content_types = parse_xml(z.read(need[0]), need[0])
            rels = parse_xml(z.read(need[1]), need[1])
            document = parse_xml(z.read(need[2]), need[2])
            body = document.find(W + "body")
            if document.tag != W + "document" or body is None:
                raise ValueError("正文根元素或body无效")
            tables = body.findall(W + "tbl")
            cells = []

            def walk_table(table: ET.Element, addr: str, depth: int) -> None:
                for ri, row in enumerate(table.findall(W + "tr")):
                    for ci, cell in enumerate(row.findall(W + "tc")):
                        where = f"{addr}/row[{ri}]/cell[{ci}]"
                        text = "".join(t.text or "" for p in cell.findall(W + "p") for t in p.iter(W + "t"))
                        tcpr = cell.find(W + "tcPr")
                        merged = tcpr is not None and (tcpr.find(W + "gridSpan") is not None or tcpr.find(W + "vMerge") is not None)
                        item = {"address": where, "nesting_depth": depth, "direct_paragraphs": len(cell.findall(W + "p")),
                                "nested_tables": len(cell.findall(W + "tbl")), "merged_marker": merged,
                                "possible_approval_text": bool(CANDIDATE.search(text))}
                        if show_text:
                            item["direct_text_preview"] = re.sub(r"\s+", " ", text).strip()[:100]
                        cells.append(item)
                        for ti, nested in enumerate(cell.findall(W + "tbl")):
                            walk_table(nested, f"{where}/table[{ti}]", depth + 1)
            for ti, t in enumerate(tables):
                walk_table(t, f"body/table[{ti}]", 0)
            counts = {
                "top_level_tables": len(tables), "all_tables_in_body": len(list(body.iter(W + "tbl"))),
                "physical_cells_listed": len(cells), "drawings": len(list(body.iter(W + "drawing"))),
                "math_objects": len(list(body.iter(M + "oMath"))),
                "insertions": len(list(body.iter(W + "ins"))), "deletions": len(list(body.iter(W + "del"))),
                "comment_markers": len(list(body.iter(W + "commentRangeStart"))),
                "field_instructions": len(list(body.iter(W + "instrText"))) + len(list(body.iter(W + "fldSimple"))),
            }
            extras = {"comments_part": "word/comments.xml" in names, "footnotes_part": "word/footnotes.xml" in names,
                      "endnotes_part": "word/endnotes.xml" in names, "header_parts": sum(bool(re.fullmatch(r"word/header\d+\.xml", n)) for n in names),
                      "footer_parts": sum(bool(re.fullmatch(r"word/footer\d+\.xml", n)) for n in names),
                      "macros_part": any(n.lower().endswith("vbaproject.bin") for n in names)}
            return {"status": "partial_structure_inspected", "input": str(path), "counts": counts,
                    "cells": cells, "package_features": extras,
                    "limits": ["仅检查三个必要XML部件，不验证全部包关系或所有部件校验和。",
                               "地址为物理XML单元格索引；合并单元格、文本框和内容控件不保证完整映射。",
                               "审批关键词只是提示，不能识别或证明所有签章栏。",
                               "未检查引用、公式含义、事实、学校规范、可视分页或可安全写入性。"],
                    "read_only": True, "text_preview_enabled": show_text}
    except (zipfile.BadZipFile, KeyError, RuntimeError, OSError) as exc:
        raise ValueError(f"无法读取DOCX压缩包：{exc}") from exc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("file", type=Path, help="待检查的.docx（只读）")
    ap.add_argument("--show-text", action="store_true", help="显示每个单元格直接段落的前100字符；可能包含个人信息")
    ap.add_argument("--json", action="store_true", help="以JSON输出")
    args = ap.parse_args(argv)
    try:
        report = inspect(args.file, args.show_text)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("检查状态：部分结构已读取（不是完整验证）")
        print("统计：" + "；".join(f"{k}={v}" for k, v in report["counts"].items()))
        print("其他部件：" + "；".join(f"{k}={v}" for k, v in report["package_features"].items()))
        for c in report["cells"]:
            row = f"{c['address']}  段落={c['direct_paragraphs']} 嵌套表={c['nested_tables']} 合并标记={c['merged_marker']} 可能审批文本={c['possible_approval_text']}"
            if args.show_text:
                row += "  文本=" + c["direct_text_preview"]
            print(row)
        print("局限：" + " ".join(report["limits"]))
        print("只读：是；内容预览：" + ("开" if args.show_text else "关"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
