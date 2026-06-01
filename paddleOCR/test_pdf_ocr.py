"""测试 PDF 文档 OCR 识别 —— 独立脚本"""
import base64
import json
import re
from html import unescape
from pathlib import Path

import requests

OCR_URL = "http://10.17.150.235:8000/layout-parsing"

pdf_path = "./1225229732.pdf"

b64_str = base64.b64encode(Path(pdf_path).read_bytes()).decode("ascii")

payload = {
    "file": b64_str,
    "fileType": 0,
    "promptLabel": "ocr",
    "visualize": False,
    "useChartRecognition": False,
    "useSealRecognition": False,
    "outputFormats": [],
}

print(f"🔍 正在识别: {pdf_path}")
resp = requests.post(OCR_URL, json=payload)
resp.raise_for_status()

results = resp.json().get("result", {}).get("layoutParsingResults", [])
texts = []
for res in results:
    raw = res.get("markdown", {}).get("text", "")
    raw = re.sub(r"<[^>]+>", "", raw)
    raw = unescape(raw)
    texts.append(raw)

full_text = "\n".join(texts)

if not full_text.strip():
    print("⚠️ 未识别到有效文本")
else:
    out_path = Path(pdf_path).with_suffix(".md")
    out_path.write_text(full_text, encoding="utf-8")
    print(f"✅ 结果已保存至: {out_path}")
    print(f"--- 共 {len(full_text)} 字符 ---")
