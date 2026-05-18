import base64
import requests
import json
from pathlib import Path

# --- 配置信息 ---
OCR_URL = "http://10.17.150.235:8000/layout-parsing"
AI_CONFIG = {
    "API_BASE_URL": "http://10.17.150.235:8001/v1/chat/completions",
    "MODEL": "/models/Qwen/Qwen3-30B-A3B-Instruct-2507",
    "TEMPERATURE": 0.6,
    "MAX_TOKENS": 4096
}


def extract_info_with_ai(text):
    """调用 Qwen3 AI 提取编号信息"""
    prompt = f"""
    请从以下 OCR 识别的文本中提取“编号”信息。
    要求：
    1. 严格返回 JSON 格式。
    2. JSON 键名为 "id_number"。
    3. 如果找不到，则返回 null。

    文本内容：
    {text}
    """

    payload = {
        "model": AI_CONFIG["MODEL"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": AI_CONFIG["TEMPERATURE"],
        "max_tokens": AI_CONFIG["MAX_TOKENS"],
        "response_format": {"type": "json_object"}  # 强制要求返回 JSON
    }

    try:
        response = requests.post(AI_CONFIG["API_BASE_URL"], json=payload, timeout=60)
        response.raise_for_status()
        ai_res = response.json()
        # 解析 AI 返回的 JSON 字符串
        content = ai_res['choices'][0]['message']['content']
        return json.loads(content)
    except Exception as e:
        print(f"❌ AI 提取失败: {e}")
        return None


def call_full_pipeline(img_path):
    try:
        # 1. OCR 识别阶段
        b64_str = base64.b64encode(Path(img_path).read_bytes()).decode("ascii")
        ocr_payload = {
            "file": b64_str,
            "fileType": 1,
            "promptLabel": "ocr",
            "visualize": False,
            "useChartRecognition": False,
            "useSealRecognition": False,
            "outputFormats": []
        }

        print("🔍 正在进行 OCR 识别...")
        ocr_resp = requests.post(OCR_URL, json=ocr_payload)
        ocr_resp.raise_for_status()

        # 2. 提取文本内容
        results = ocr_resp.json().get("result", {}).get("layoutParsingResults", [])
        full_text = "\n".join([res.get("markdown", {}).get("text", "") for res in results])

        if not full_text.strip():
            print("⚠️ 未识别到有效文本")
            return

        # 3. AI 结构化提取阶段
        print("🤖 正在调用 AI 提取编号...")
        final_json = extract_info_with_ai(full_text)

        if final_json:
            print("\n✨ 最终提取结果 (JSON):")
            print(json.dumps(final_json, indent=4, ensure_ascii=False))

    except Exception as e:
        print(f"⚠️ 流程异常: {e}")


if __name__ == "__main__":
    call_full_pipeline("./IMG_20260507_142952.jpg")