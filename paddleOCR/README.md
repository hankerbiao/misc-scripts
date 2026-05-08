# PaddleOCR - AI 图片信息提取工具

使用 PaddleOCR 进行图片文字识别，结合 AI 模型提取结构化信息。

## 功能

- 图片 OCR 识别（布局分析）
- 调用 Qwen3 AI 模型进行结构化信息提取
- 从识别文本中提取"编号"信息

## API 配置

- Layout Parsing: `http://10.17.150.235:8000/layout-parsing`
- AI API: `http://10.17.150.235:8001/v1/chat/completions`
- AI Model: `/models/Qwen/Qwen3-30B-A3B-Instruct-2507`

## 依赖

```bash
pip install requests
```

## 使用方法

修改脚本末尾的图片路径后运行：

```bash
python paddleOCR.py
```

默认处理 `./IMG_20260507_143000.jpg`

## 处理流程

1. **OCR 识别阶段**: 使用 layout-parsing 接口识别图片中的文字和布局
2. **AI 提取阶段**: 调用 Qwen3 模型从识别文本中提取结构化的"编号"信息
3. **结果输出**: 以 JSON 格式展示最终提取结果