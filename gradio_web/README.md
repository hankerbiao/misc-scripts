# Gradio Web - OCR 图片识别测试工具

基于 Gradio 的 OCR 图片识别 Web 界面。

## 功能

- 上传图片进行 OCR 识别
- 支持从本地上传或摄像头拍照
- 显示 JSON 格式的识别结果
- 提取并展示纯文本内容

## API 配置

- OCR API: `http://10.17.150.235:8001/ocr`

## 依赖

```bash
pip install gradio requests
```

## 运行

```bash
python gradio_web.py
```

启动后访问 `http://localhost:7860`