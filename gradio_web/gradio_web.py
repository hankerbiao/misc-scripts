import gradio as gr
import requests

# API 配置
API_URL = "http://10.17.150.235:8001/ocr"


def ocr_recognition(image_path):
    """
    发送图片到 OCR API 进行识别
    """
    try:
        with open(image_path, "rb") as f:
            response = requests.post(
                API_URL,
                files={"file": f},
                data={
                    "crop_mode": False,
                    "max_crops": 9,
                    "prompt": "<image>\n<|grounding|>OCR all text in this image,preserve layout.",
                    "min_crops": 1
                },
                timeout=300
            )

        if response.status_code == 200:
            result = response.json()
            return result
        else:
            return {"error": f"HTTP {response.status_code}", "message": response.text}

    except requests.exceptions.ConnectionError:
        return {"error": "连接失败", "message": f"无法连接到 {API_URL}"}
    except requests.exceptions.Timeout:
        return {"error": "请求超时", "message": "服务器响应时间过长"}
    except Exception as e:
        return {"error": "请求异常", "message": str(e)}


# 创建 Gradio 界面
with gr.Blocks(title="OCR 图片识别测试") as demo:
    gr.Markdown("# 📝 OCR 图片识别测试工具")
    gr.Markdown(f"测试接口: `{API_URL}`")

    with gr.Row():
        with gr.Column():
            # 图片输入
            image_input = gr.Image(
                type="filepath",
                label="上传图片",
                sources=["upload", "webcam"]
            )

            # 按钮
            with gr.Row():
                submit_btn = gr.Button("🔍 开始识别", variant="primary")
                clear_btn = gr.Button("🗑️ 清空")

        with gr.Column():
            # 结果显示
            result_output = gr.JSON(
                label="识别结果 (JSON)",
                value={}
            )

            # 文本提取显示
            text_output = gr.Textbox(
                label="提取文本",
                lines=5,
                interactive=False
            )


    def process_result(image):
        if image is None:
            return {}, "请先上传图片"

        result = ocr_recognition(image)

        # 尝试提取文本字段
        extracted_text = ""
        if isinstance(result, dict):
            possible_text_keys = ["text", "content", "result", "ocr_text", "data", "recognition"]
            for key in possible_text_keys:
                if key in result:
                    extracted_text = str(result[key])
                    break
            if not extracted_text:
                extracted_text = str(result)
        else:
            extracted_text = str(result)

        return result, extracted_text


    # 绑定事件
    submit_btn.click(
        fn=process_result,
        inputs=image_input,
        outputs=[result_output, text_output]
    )

    clear_btn.click(
        fn=lambda: (None, {}, ""),
        inputs=None,
        outputs=[image_input, result_output, text_output]
    )

# 启动
if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860
    )
