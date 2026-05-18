import ast
import json
import os
import requests
from datetime import datetime


# ==========================================
# 1. 核心工具类定义
# ==========================================

class ImportAnalyzer(ast.NodeVisitor):
    """
    分析目标文件，提取出所有的 import 和 from ... import 语句
    """

    def __init__(self):
        self.dependencies = []

    def visit_ImportFrom(self, node):
        # 处理 from x import y
        module = node.module if node.module else ""
        for alias in node.names:
            self.dependencies.append({
                "type": "from_import",
                "module": module,
                "name": alias.name,
                "line": node.lineno
            })
        self.generic_visit(node)

    def visit_Import(self, node):
        # 处理 import x
        for alias in node.names:
            self.dependencies.append({
                "type": "import",
                "module": alias.name,
                "name": "*",
                "line": node.lineno
            })
        self.generic_visit(node)


class CodeBlockExtractor(ast.NodeVisitor):
    """
    在依赖文件中，根据函数名或类名，精准查找其所在的开始行和结束行
    """

    def __init__(self, target_name):
        self.target_name = target_name
        self.start_line = None
        self.end_line = None

    def _check_name(self, node):
        if node.name == self.target_name:
            self.start_line = node.lineno
            self.end_line = node.end_lineno

    def visit_FunctionDef(self, node):
        self._check_name(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self._check_name(node)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self._check_name(node)
        self.generic_visit(node)


# ==========================================
# 2. 业务逻辑封装
# ==========================================

def get_code_slice(file_path, target_name):
    """
    从指定文件中精准切出某个函数或类的源码
    """
    if not os.path.exists(file_path):
        return f"# 错误: 未找到依赖文件 {file_path}\n"

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    try:
        tree = ast.parse("".join(lines))
        extractor = CodeBlockExtractor(target_name)
        extractor.visit(tree)

        if extractor.start_line and extractor.end_line:
            # AST 行号从 1 开始，切片从 0 开始
            sliced_lines = lines[extractor.start_line - 1: extractor.end_line]
            return "".join(sliced_lines)
        else:
            return f"# 提示: 在 {file_path} 中未匹配到 [{target_name}] 的具体具体定义（可能是第三方库或内置模块）\n"
    except Exception as e:
        return f"# 解析 {file_path} 失败: {e}\n"


def generate_llm_context(main_file_path, project_root="."):
    """
    主控函数：输入主文件，输出大模型所需的高保真精简上下文
    返回: (prompt_text, analysis_result) 元组
    """
    if not os.path.exists(main_file_path):
        print(f"主文件 {main_file_path} 不存在！")
        return None, None

    with open(main_file_path, "r", encoding="utf-8") as f:
        main_code = f.read()

    # 第一步：分析主文件的依赖
    tree = ast.parse(main_code)
    analyzer = ImportAnalyzer()
    analyzer.visit(tree)

    # 第二步：收集所有本地依赖的源码切片
    extracted_dependencies = {}
    local_dependencies = []  # 保存本地依赖信息用于AST分析结果

    for dep in analyzer.dependencies:
        # 我们只处理 from ... import 形式的具体函数/类引用
        if dep["type"] == "from_import" and dep["module"]:
            # 将模块路径转换为本地文件路径 (例如: utils.math_tools -> utils/math_tools.py)
            relative_path = dep["module"].replace(".", "/") + ".py"
            target_file_path = os.path.join(project_root, relative_path)
            target_name = dep["name"]

            # 如果该文件在本地存在，说明是自定义模块，开始切片
            if os.path.exists(target_file_path):
                key = f"{relative_path} -> {target_name}"
                if key not in extracted_dependencies:
                    code_block = get_code_slice(target_file_path, target_name)
                    extracted_dependencies[key] = code_block
                    local_dependencies.append({
                        "module": dep["module"],
                        "name": target_name,
                        "relative_path": relative_path,
                        "target_file_path": target_file_path,
                        "line": dep["line"]
                    })

    # 第三步：组装最终喂给大模型的 Prompt 文本
    prompt_output = []
    prompt_output.append("=== 【任务上下文开始】 ===")
    prompt_output.append(f"\n【主文件源码: {os.path.basename(main_file_path)}】")
    prompt_output.append("```python")
    prompt_output.append(main_code)
    prompt_output.append("```\n")

    if extracted_dependencies:
        prompt_output.append("【以下是主文件依赖的本地模块核心代码片段，已过滤无关逻辑】")
    for ref, code in extracted_dependencies.items():
        prompt_output.append(f"// 摘自本地依赖: {ref}")
        prompt_output.append("```python")
        prompt_output.append(code.strip("\n"))
        prompt_output.append("```\n")
    else:
        prompt_output.append("【提示: 未检测到本地自定义模块的深度依赖。】\n")

        prompt_output.append("=== 【任务上下文结束】 ===")

    prompt_text = "\n".join(prompt_output)

    # 构建分析结果
    analysis_result = {
        "main_file": main_file_path,
        "project_root": project_root,
        "all_dependencies": analyzer.dependencies,
        "local_dependencies": local_dependencies,
        "extracted_dependencies": list(extracted_dependencies.keys()),
        "main_code_preview": main_code[:500] + "..." if len(main_code) > 500 else main_code
    }

    return prompt_text, analysis_result


# ==========================================
# 3. AI 分析模块
# ==========================================

AI_CONFIG = {
    "base_url": "http://10.41.101.220:8000/v1",
    "model": "/models/coder/minimax/MiniMax-M2"
}


def analyze_with_ai(ast_result_file: str, output_dir: str,
                    stream: bool = True, timeout: int = 600,
                    max_tokens: int = 8192, temperature: float = 0.3) -> str:
    """
    使用 AI 分析 AST 结果 JSON，生成可读的 Markdown 报告
    参数:
        stream: 是否使用流式输出
        timeout: 请求超时时间（秒）
        max_tokens: 最大输出 token 数
        temperature: 温度参数
    返回: Markdown 文件路径
    """
    # 读取 AST 分析结果
    with open(ast_result_file, "r", encoding="utf-8") as f:
        ast_data = json.load(f)

    # 构建 AI Prompt
    report_template = """报告格式模板（参考此格式生成）：

# [主文件名] 代码分析报告

## 项目概览

| 属性 | 值 |
|------|-----|
| **主文件** | `[文件名]` |
| **完整路径** | `[完整路径]` |
| **项目根目录** | `[根目录]` |

---

## 项目依赖统计

| 统计项 | 数量 |
|--------|------|
| **总依赖数** | N |
| **本地依赖数** | N |
| **第三方依赖数** | N |

### 第三方依赖（标准库 + 第三方库）

| 模块名 | 导入类型 | 行号 |
|--------|----------|------|
| `os` | import | 5 |

---

## 本地依赖详情

### 1. [模块路径]

| 函数/类名 | 导入语句 | 行号 |
|-----------|----------|------|
| `FuncName` | `from xxx import xxx` | N |

**功能说明**: 功能描述

---

## 本地依赖依赖关系图

```
主文件
├── 模块1
│   └── 函数/类
└── 模块2
    └── 函数/类
```

---

## 代码结构总结

### 整体架构

[用文字描述整体架构]

### 模块分组

| 分组 | 模块 | 核心功能 |
|------|------|----------|
| **分组名** | `模块` | 功能 |

---

## AI 分析总结

### 项目特点

1. 特点1
2. 特点2

### 依赖关系评估

- 评估内容

### 建议

1. 建议1
"""

    system_prompt = f"""你是一个专业的代码分析助手。你的任务是根据提供的 AST 分析结果，生成一个专业、结构化的 Markdown 格式分析报告。

重要约束：
1. **禁止思考**：不要输出任何<think>、</think>标签或思考过程
2. **直接输出**：只输出最终的分析报告内容
3. **格式规范**：严格按照【报告格式模板】的格式生成报告
4. **中文描述**：用中文描述所有内容
5. **详细说明**：所有模块都要有【功能说明】
6. **清晰结构**：依赖关系图要展示模块调用关系
7. **完整总结**：包含项目特点、依赖评估、建议

【报告格式模板】
{report_template}

只返回纯 Markdown 内容，不要有任何额外说明，不要用 ```markdown 或 ``` 包裹，不要输出思考过程。"""

    user_prompt = f"""请分析以下 AST 分析结果，生成 Markdown 格式的分析报告：

```json
{json.dumps(ast_data, ensure_ascii=False, indent=2)}
```

按照系统提示中的【报告格式模板】生成专业的分析报告。"""

    print(f"\n   正在调用 AI 模型生成 Markdown 报告{'（流式输出）' if stream else ''}...")
    print("-" * 50)

    api_url = f"{AI_CONFIG['base_url']}/chat/completions"
    print(f"   [DEBUG] API URL: {api_url}")
    print(f"   [DEBUG] Model: {AI_CONFIG['model']}")

    request_data = {
        "model": AI_CONFIG["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream
    }
    print(f"   [DEBUG] Request data size: {len(str(request_data))} bytes")

    try:
        print("   [DEBUG] 发送流式请求中...")

        # 流式请求
        response = requests.post(
            api_url,
            json=request_data,
            stream=stream,
            timeout=timeout
        )
        print(f"   [DEBUG] Response status: {response.status_code}")
        response.raise_for_status()

        # 收集流式内容
        full_content = []
        char_count = 0

        print("\n   [AI 输出开始]")
        for line in response.iter_lines():
            if line:
                line_text = line.decode('utf-8')
                # SSE 格式: data: {...}
                if line_text.startswith("data: "):
                    data_str = line_text[6:]  # 去掉 "data: " 前缀
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        if "choices" in data and len(data["choices"]) > 0:
                            delta = data["choices"][0].get("delta", {})
                            if "content" in delta:
                                content = delta["content"]
                                full_content.append(content)
                                char_count += len(content)
                                # 实时打印
                                print(content, end="", flush=True)
                    except json.JSONDecodeError:
                        continue

        print("\n   [AI 输出结束]")
        print(f"   [DEBUG] 总输出字符数: {char_count}")

        md_content = "".join(full_content)

        # 过滤 AI 思考内容
        import re
        # 移除 <|im_start|> 和 <|im_end|> 标签及其内容
        md_content = re.sub(r'<\|im_start\|>.*?<\|im_end\|>', '', md_content, flags=re.DOTALL)
        # 移除<think>、</think>标签及内容
        md_content = re.sub(r'<think>.*?</think>', '', md_content, flags=re.DOTALL)
        # 移除所有 <|...|> 格式的标签
        md_content = re.sub(r'<\|[^|]*\|>', '', md_content)

        # 清理可能的 markdown 代码块包裹
        md_content = md_content.strip()
        if md_content.startswith("```markdown"):
            md_content = md_content[len("```markdown"):]
        if md_content.startswith("```"):
            md_content = md_content.split("```")[1]
        if md_content.endswith("```"):
            md_content = md_content[:-3]
        md_content = md_content.strip()

        # 移除空行过多的连续空行
        md_content = re.sub(r'\n{4,}', '\n\n\n', md_content)

        print(f"   [DEBUG] 清理后 Markdown 长度: {len(md_content)} chars")

        if not md_content:
            print("   ✗ Markdown 内容为空")
            return None

        # 保存 Markdown 文件
        md_file = os.path.join(output_dir, "AI分析报告.md")
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(md_content)

        print("-" * 50)
        print(f"   ✓ Markdown 报告已生成: {md_file}")
        return md_file

    except requests.exceptions.Timeout:
        print(f"   ✗ AI 请求超时 ({timeout}秒)")
        return None
    except requests.exceptions.ConnectionError as e:
        print(f"   ✗ 连接失败: {e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"   ✗ AI 请求失败: {e}")
        return None
    except Exception as e:
        print(f"   ✗ 未知错误: {e}")
        import traceback
        print(f"   [DEBUG] {traceback.format_exc()}")
        return None


if __name__ == "__main__":
    import argparse

    # ==========================================
    # 4. 运行配置
    # ==========================================

    # 命令行参数解析
    parser = argparse.ArgumentParser(description="AST 依赖分析工具")
    parser.add_argument("--file", "-f", type=str, default=None,
                        help="要分析的主文件路径（相对于 PROJECT_ROOT）")
    parser.add_argument("--root", "-r", type=str, default=None,
                        help="项目根目录路径")
    args = parser.parse_args()

    # 路径配置（命令行参数 > 默认值）
    PROJECT_ROOT = args.root or "/Users/libiao/Desktop/gitlab/bmc_suite_performance_universal/performance"
    MAIN_FILE = args.file or "TestCases/Perform/IPMI/IPMI_performance.py"
    main_file_path = os.path.join(PROJECT_ROOT, MAIN_FILE)

    # AI 分析开关
    AI_ENABLE = True              # 是否启用 AI 分析 AST 结果
    AI_STREAM = True              # 是否启用流式输出
    AI_TIMEOUT = 600               # AI 请求超时时间（秒）
    AI_MAX_TOKENS = 8192           # AI 最大输出 token 数
    AI_TEMPERATURE = 0.3           # AI temperature 参数

    # ==========================================
    # 5. 执行主流程
    # ==========================================

    # 创建输出目录（使用被处理文件名作为目录名）
    main_file_name = os.path.splitext(os.path.basename(MAIN_FILE))[0]
    output_dir = os.path.join(PROJECT_ROOT, f"ast_output_{main_file_name}")
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("AST 依赖分析工具")
    print("=" * 60)

    print("\n【配置信息】")
    print(f"   主文件: {main_file_path}")
    print(f"   项目根目录: {PROJECT_ROOT}")
    print(f"   输出目录: {output_dir}")
    print(f"   AI 分析: {'启用' if AI_ENABLE else '禁用'}")
    if AI_ENABLE:
        print(f"   AI API: {AI_CONFIG['base_url']}")
        print(f"   AI 模型: {AI_CONFIG['model']}")
        print(f"   AI 流式: {'启用' if AI_STREAM else '禁用'}")

    print("\n1. 正在通过 AST 分析依赖并裁剪代码...")
    final_prompt_for_llm, analysis_result = generate_llm_context(main_file_path, PROJECT_ROOT)

    if final_prompt_for_llm and analysis_result:
        # 保存AST分析结果
        ast_result_file = os.path.join(output_dir, "AST分析结果.json")
        with open(ast_result_file, "w", encoding="utf-8") as f:
            json.dump(analysis_result, f, ensure_ascii=False, indent=2)

        # 保存给大模型的干净文本
        llm_context_file = os.path.join(output_dir, "大模型上下文.txt")
        with open(llm_context_file, "w", encoding="utf-8") as f:
            f.write(final_prompt_for_llm)

        print(f"   ✓ 已保存: AST分析结果.json")
        print(f"   ✓ 已保存: 大模型上下文.txt")

        # AI 分析（可选）
        if AI_ENABLE:
            print(f"\n2. 正在通过 AI 生成 Markdown 分析报告...")
            md_file = analyze_with_ai(ast_result_file, output_dir,
                                       stream=AI_STREAM,
                                       timeout=AI_TIMEOUT,
                                       max_tokens=AI_MAX_TOKENS,
                                       temperature=AI_TEMPERATURE)
        else:
            print("\n2. [跳过] AI 分析已禁用")
            md_file = None

        print(f"\n【输出文件】{output_dir}:")
        print(f"   - AST分析结果.json (依赖分析详情)")
        print(f"   - 大模型上下文.txt (最终Prompt)")
        if md_file:
            print(f"   - AI分析报告.md (AI 生成的分析报告)")

        print("\n【大模型上下文预览】:")
        print("-" * 60)
        print(final_prompt_for_llm[:2000] + "..." if len(final_prompt_for_llm) > 2000 else final_prompt_for_llm)
        print("-" * 60)

        print(f"\n✓ 分析完成！")
        print(f"  输出目录: {output_dir}")
    else:
        print("分析失败！")