"""PDF 文档 OCR 识别 —— 独立脚本，不依赖 paddleOCR.py"""
import base64
import json
import requests
from pathlib import Path

OCR_URL = "http://10.17.150.235:8000/layout-parsing"


def ocr_pdf(pdf_path: str) -> str | None:
    """对 PDF 文件执行 OCR，返回识别到的全部文本"""
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
    full_text = "\n".join(
        res.get("markdown", {}).get("text", "") for res in results
    )

    if not full_text.strip():
        print("⚠️ 未识别到有效文本")
        return None

    return full_text


if __name__ == "__main__":
    text = ocr_pdf("./1225229732.pdf")
    if text:
        print("\n📄 识别结果:\n")
        print(text)
        print(f"\n--- 共 {len(text)} 字符 ---")
