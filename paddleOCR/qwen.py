import base64
import requests
import json

# 配置
API_URL = "http://10.8.136.35:8081/v1/chat/completions"
API_KEY = ""
MODEL = "Qwen3.6-35B-A3B"


def recognize_text_from_image(image_path):
    """识别图片中的文字"""

    # 1. 读取并编码图片
    with open(image_path, "rb") as f:
        image_data = f.read()
        base64_image = base64.b64encode(image_data).decode('utf-8')

    # 2. 构建请求
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "请识别这张图片中的所有文字"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        "temperature": 0.1,
        "max_tokens": 500
    }

    # 3. 发送请求
    response = requests.post(API_URL, headers=headers, json=payload)

    # 4. 解析结果
    if response.status_code == 200:
        result = response.json()
        text = result["choices"][0]["message"]["content"]
        return text
    else:
        print(f"错误: {response.status_code}")
        return None


# 使用示例
if __name__ == "__main__":
    # 识别图片中的文字
    result = recognize_text_from_image("IMG_20260507_142952.jpg")
    if result:
        print("识别结果:")
        print(result)
