#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多源比对：仓库知识点章节树 vs 杭州人教版小学教材目录。

只读工具，不修改任何数据文件。用于「多轮比对并选出最新最合理的」：
把四个来源放在同一张表里，按优先级裁决，输出 Markdown 报告与可选 JSON。

来源优先级（高 -> 低），详见 docs/hangzhou-alignment.md：
  P1 教材 PDF 目录        杭州人教版小学/<科目>/教材/*.pdf（实物教材，最权威）
  P2 教材清单.csv         版本口径（哪一册是 2022 课标修订版 / 旧课标版）
  P3 学习材料/ 目录树     平台课时包落盘后的目录名
  P4 _build/docs_plan.json 平台原始课时树（可能是另一版/旧版，仅作参考）
  T  data/topics.json     待校验的代码侧章节树

用法（在仓库根目录）：
  python scripts/align_hangzhou.py
  python scripts/align_hangzhou.py --hangzhou "D:/.../杭州人教版小学" --out align_report.md --json align_report.json
  python scripts/align_hangzhou.py --no-pdf          # 无 PyMuPDF 时跳过 P1

依赖：标准库；P1 需要 PyMuPDF（pymupdf / fitz），缺失时自动降级并标注。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_HANGZHOU = os.path.normpath(os.path.join(ROOT, "..", "杭州人教版小学"))

CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
SUBJECT_PREFIX = {
    "数学": "cnm", "语文": "cnc", "英语": "cne",
    "科学": "cns", "道德与法治": "cnd",
}
CATALOG_DIR = {
    "01 语文（统编版）": "语文",
    "02 数学（人教版）": "数学",
    "03 英语（人教版 PEP·三年级起点）": "英语",
    "04 道德与法治（统编版）": "道德与法治",
    "05 科学（教科版）": "科学",
}
PLAN_SUBJECT = {"数学": "数学", "语文": "语文", "英语": "英语", "科学": "科学", "道德与法治": "道德与法治"}


def norm(s: str) -> str:
    """归一化：全角转半角、去空白与标点，保留中英文数字。"""
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = s.replace("～", "~").replace("－", "-").replace("—", "-")
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", s)


def book_to_num(book: str) -> str:
    """一年级上册 -> 1年级上册（与教材清单口径一致）。"""
    m = re.match(r"^([一二三四五六])年级([上下])册$", book or "")
    if m:
        return f"{CN_NUM[m.group(1)]}年级{m.group(2)}册"
    return book or ""


def parse_catalog(base: str):
    p = os.path.join(base, "教材清单.csv")
    out = {}
    if not os.path.exists(p):
        return out
    with open(p, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            sub = CATALOG_DIR.get(row.get("科目", "").strip())
            if not sub:
                continue
            out[(sub, row["册次"].strip())] = {
                "教材版本": row.get("教材版本", ""),
                "课标版本": row.get("课标版本", ""),
                "相对路径": row.get("相对路径", ""),
                "平台ID": row.get("平台ID", ""),
            }
    return out


def parse_platform_tree(base: str):
    """P4：平台课时树。同时记录 book.target 以便检出版本错配。"""
    p = os.path.join(base, "_build", "docs_plan.json")
    tree, targets = defaultdict(lambda: defaultdict(list)), {}
    if not os.path.exists(p):
        return tree, targets
    with open(p, encoding="utf-8") as f:
        plan = json.load(f)
    for it in plan:
        b = it.get("book", {})
        sub = PLAN_SUBJECT.get(b.get("subject"))
        if not sub:
            continue
        key = (sub, f"{b.get('grade')}年级{b.get('vol')}")
        for act in it.get("acts", []):
            unit = (act.get("chapter") or "").split("/")[0].strip()
            if unit:
                tree[key][unit].append(act.get("title", ""))
        targets[key] = b.get("target", "")
    return tree, targets


def parse_material_tree(base: str):
    """P3：学习材料目录名 '<单元> - <课时>' 的前缀即单元名。"""
    out = defaultdict(set)
    for dirname, sub in CATALOG_DIR.items():
        p = os.path.join(base, dirname, "学习材料")
        if not os.path.isdir(p):
            p = os.path.join(base, dirname, "教材")
            if not os.path.isdir(p):
                continue
        for book in os.listdir(p):
            bp = os.path.join(p, book)
            if not os.path.isdir(bp):
                continue
            for item in os.listdir(bp):
                if os.path.isdir(os.path.join(bp, item)):
                    out[(sub, book)].add(re.sub(r"\s+", " ", item.split(" - ")[0].strip()))
    return out


def parse_pdf_toc(base: str, catalog, max_pages=12, quiet=False):
    """P1：抽取每册教材 PDF 目录页原文；返回 {(学科,册次): 归一化文本}。"""
    try:
        import pymupdf as fitz
    except ImportError:
        try:
            import fitz  # type: ignore
        except ImportError:
            if not quiet:
                print("[P1] 未安装 PyMuPDF，跳过教材 PDF 目录（可用 --no-pdf 显式关闭）", file=sys.stderr)
            return {}
    out = {}
    for (sub, book), meta in catalog.items():
        if "备选" in meta.get("相对路径", ""):
            continue
        cand = [f"{book}（2022课标修订版）.pdf", f"{book}（旧课标版）.pdf"]
        # 相对路径形如 '02 数学（人教版）/教材/4年级上册（...）.pdf'
        rel = meta.get("相对路径", "")
        paths = [os.path.join(base, rel)] if rel else []
        dirname = next((k for k, v in CATALOG_DIR.items() if v == sub), "")
        for c in cand:
            paths.append(os.path.join(base, dirname, "教材", c))
        pdf = next((p for p in paths if p and os.path.exists(p)), None)
        if not pdf:
            continue
        try:
            doc = fitz.open(pdf)
            chunks = []
            marker = None
            for i in range(min(max_pages, len(doc))):
                txt = doc[i].get_text()
                if "目录" in txt or re.search(r"\bContents\b", txt):
                    marker = i
                    break
            if marker is not None:
                # 语文/道法目录常跨 2–4 页，只取标记页会漏掉后半部分
                for i in range(marker, min(marker + 4, len(doc))):
                    chunks.append(doc[i].get_text())
            doc.close()
            if chunks:
                out[(sub, book)] = norm(" ".join(chunks))
        except Exception as e:  # 单个 PDF 损坏不应中断整轮比对
            print(f"[P1] 读取失败 {book}/{sub}: {e}", file=sys.stderr)
    return out


def parse_code_tree():
    p = os.path.join(ROOT, "data", "topics.json")
    with open(p, encoding="utf-8") as f:
        topics = json.load(f)
    tree = defaultdict(lambda: defaultdict(list))
    for x in topics:
        pre = x["id"].split("_")[0]
        sub = next((k for k, v in SUBJECT_PREFIX.items() if v == pre), None)
        if not sub:
            continue
        g = x.get("grade")
        if not isinstance(g, int) or g > 6:
            continue
        book = f"{g}年级{x.get('semester', '')}册"
        m = re.match(r"^((?:[一二三四五六]|\d)年级[上下]册)\s+(.*)$", x.get("chapter") or "")
        if not m:
            tree[(sub, book)][("?", 0, x.get("chapter") or "")].append(x["id"])
            continue
        rest = m.group(2)
        m2 = re.match(r"^第(\d+)单元\s+(.+)$", rest)
        if m2:
            unit = (m2.group(2).strip(), int(m2.group(1)), "单元")
        else:
            unit = (rest.strip(), 0, "专题")
        tree[(sub, book)][unit].append(x["id"])
    return tree


UNIT_PREFIX = ("综合与实践", "数学广角", "复习与关联")
# 复合单元名里的通用分类词，单独命中会误判，有更具体的片段时优先用具体片段
GENERIC_PARTS = {
    "课文", "古诗", "识字", "阅读", "文言文", "童话", "寓言", "传说", "习作",
    "口语", "复习", "汉语拼音", "综合", "实践", "整理", "单元", "数学",
}


def strip_unit_prefix(s: str) -> str:
    """剥离 '一  xxx' / '一、xxx' / '第一单元·识字' / 'Unit 1 xxx' 等单元序号前缀。"""
    s = (s or "").strip()
    s = re.sub(r"^第[一二三四五六七八九十\d]+单元\s*[·・]?\s*", "", s)
    s = re.sub(r"^[一二三四五六七八九十]+\s*[、.,·]?\s*", "", s)
    s = re.sub(r"^Unit\s*\d+\s+", "", s, flags=re.I)
    return s.strip()


def unit_variants(name: str):
    """代码单元名可能有 '综合与实践 寻找宝藏'、'识字·天地人' 这类复合名，
    拆出可用于命中的片段；单字单元名（如「圆」）也保留。"""
    parts = [name]
    stripped = name.strip()
    for pre in UNIT_PREFIX:
        if stripped.startswith(pre):
            tail = stripped[len(pre):].strip(" ·—-")
            if tail:
                parts.append(tail)
    if "·" in name:
        parts.extend(p.strip() for p in name.split("·") if p.strip())
    for sep in ("——", "—", "--"):
        if sep in name:
            parts.extend(p.strip() for p in name.split(sep) if p.strip())
    allv = []
    for p in parts:
        n = norm(p)
        if n and n not in allv:
            allv.append(n)
    specific = [v for v in allv if v not in {norm(g) for g in GENERIC_PARTS}]
    return specific or allv


def main():
    ap = argparse.ArgumentParser(description="多源比对：知识点章节树 vs 杭州教材目录")
    ap.add_argument("--hangzhou", default=DEFAULT_HANGZHOU, help="杭州人教版小学目录路径")
    ap.add_argument("--out", default=os.path.join(ROOT, "align-report.md"), help="Markdown 报告输出路径")
    ap.add_argument("--json", dest="json_out", default="", help="可选：机器可读 JSON 差异输出路径")
    ap.add_argument("--no-pdf", action="store_true", help="跳过 P1 教材 PDF 目录抽取")
    args = ap.parse_args()

    base = os.path.abspath(args.hangzhou)
    if not os.path.isdir(base):
        print(f"错误：找不到杭州教材目录 {base}", file=sys.stderr)
        return 2

    catalog = parse_catalog(base)
    platform, targets = parse_platform_tree(base)
    materials = parse_material_tree(base)
    pdf_toc = {} if args.no_pdf else parse_pdf_toc(base, catalog)
    code = parse_code_tree()

    report, machine = [], []
    report.append("# 知识点章节树 · 多源比对报告")
    report.append("")
    report.append(f"- 杭州目录：`{base}`")
    report.append(f"- 代码数据：`{os.path.join(ROOT, 'data', 'topics.json')}`")
    report.append("- 来源优先级：**P1 教材 PDF 目录 > P2 教材清单版本 > P3 学习材料目录 > P4 平台课时树**；T = 待校验的代码章节树")
    report.append("- P1 命中方式：代码单元名（含 `·` 拆分片段）归一化后，是否为教材目录页原文的子串。")
    report.append("- 本工具只读，不修改任何数据。规则与裁决见 `docs/hangzhou-alignment.md`。")
    report.append("")
    if not pdf_toc:
        report.append("> ⚠️ 本轮未启用 P1（教材 PDF 目录），裁决退到 P3/P4，结论置信度下降。")
        report.append("")

    # 版本错配：平台课时树 target 指向的教材版本 与 教材清单声明不一致
    mismatches = []
    for key, target in targets.items():
        meta = catalog.get(key)
        if not meta or not target:
            continue
        listed = meta.get("相对路径", "")
        if listed and os.path.normpath(target) != os.path.normpath(listed):
            mismatches.append((key, meta.get("教材版本", ""), listed, target))
    if mismatches:
        report.append("## ⚠️ 平台课时树版本错配（P4 不可作为该册权威源）")
        report.append("")
        report.append("| 册次 | 清单声明版本 | 清单路径 | 平台课时树实际指向 |")
        report.append("|---|---|---|---|")
        for key, ver, listed, target in sorted(mismatches):
            report.append(f"| {key[0]} {key[1]} | {ver} | `{listed}` | `{target}` |")
        report.append("")

    stats = defaultdict(int)
    subjects = sorted({k[0] for k in code} | {k[0] for k in catalog})
    for sub in subjects:
        books = sorted({k[1] for k in code if k[0] == sub} | {k[1] for k in catalog if k[0] == sub})
        report.append(f"\n## {sub}")
        report.append("")
        report.append("| 册次 | 教材版本 | 权威源 | 代码单元 | P1 命中 | 未命中单元 | P4 不符教材目录 |")
        report.append("|---|---|---|---:|---:|---|---:|")
        for book in books:
            meta = catalog.get((sub, book), {})
            units = code.get((sub, book), {})
            toc = pdf_toc.get((sub, book))
            mat = materials.get((sub, book), set())
            plat = platform.get((sub, book), {})
            hit, miss = [], []
            for (name, num, kind), ids in units.items():
                variants = unit_variants(name)
                ok = bool(toc) and any(v in toc for v in variants)
                (hit if ok else miss).append((name, len(ids), ok))
            if toc:
                source = "P1 教材 PDF 目录"
            elif mat:
                source = "P3 学习材料目录"
            elif plat:
                source = "P4 平台课时树（低置信）"
            else:
                source = "无权威源"
            # P3 补充验证：目录里能找到同名单元也算命中
            if not toc and mat:
                norm_mat = [norm(m) for m in mat]
                for name, n, _ in list(miss):
                    if any(v in nm for v in unit_variants(name) for nm in norm_mat if len(nm) > 1):
                        hit.append((name, n, True))
                        miss.remove((name, n, False))
            if toc and plat:
                p4diff = sum(1 for u in plat
                             if all(norm(v) not in toc for v in unit_variants(strip_unit_prefix(u))))
            elif plat and mat:
                p4diff = len(set(norm(strip_unit_prefix(u)) for u in plat)
                             - set(norm(strip_unit_prefix(m)) for m in mat))
            else:
                p4diff = "—"
            miss_str = "、".join(f"{m[0]}({m[1]})" for m in miss[:4]) or "—"
            if len(miss) > 4:
                miss_str += f" 等 {len(miss)} 项"
            report.append(
                f"| {book} | {meta.get('课标版本','—')} | {source} | {len(units)} | "
                f"{len(hit)}/{len(units)} | {miss_str} | {p4diff} |"
            )
            stats["books"] += 1
            stats["units"] += len(units)
            stats["hit"] += len(hit)
            stats["miss"] += len(miss)
            machine.append({
                "subject": sub, "book": book,
                "课标版本": meta.get("课标版本", ""),
                "教材版本": meta.get("教材版本", ""),
                "权威源": source,
                "代码单元": len(units),
                "P1命中": len(hit),
                "未命中": [m[0] for m in miss],
                "平台树单元": sorted(plat),
                "学习材料单元": sorted(mat),
                "平台树target": targets.get((sub, book), ""),
            })

    report.append("")
    report.append("## 汇总")
    report.append("")
    rate = (stats["hit"] / stats["units"] * 100) if stats["units"] else 0
    report.append(f"- 比对册次 **{stats['books']}**，代码单元 **{stats['units']}** 个，权威源命中 **{stats['hit']}** 个（{rate:.1f}%），未命中 **{stats['miss']}** 个。")
    report.append("- 未命中不等于错误：可能是综合与实践专题、跨册迁移点、或教材尚未收录的拓展知识点，需结合 `standards[].note` 与 `docs/hangzhou-alignment.md` 的裁决记录逐项判断。")
    report.append("- 平台课时树（P4）与实物教材不同名时，**以教材 PDF 目录为准**，不要据 P4 直接改代码。")
    report.append("")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump({"summary": dict(stats), "version_mismatch": [
                {"subject": k[0], "book": k[1], "版本": v, "清单路径": a, "平台指向": b}
                for k, v, a, b in mismatches
            ], "books": machine}, f, ensure_ascii=False, indent=2)
    print(f"报告已写入 {args.out}")
    print(f"汇总：册次 {stats['books']}，代码单元 {stats['units']}，命中 {stats['hit']}（{rate:.1f}%），未命中 {stats['miss']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
