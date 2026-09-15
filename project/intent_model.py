import json
import re
import os
from openai import OpenAI

class IntentParser:
    def __init__(self, db_path: str = "database.json", prompt_path: str = "./prompt/intent_model.md"):
        self.db_path = db_path
        self.prompt_path = prompt_path

        # 初始化阿里云 Qwen 客户端（API Key 从环境变量读取，不写入代码库）
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise EnvironmentError(
                "未设置环境变量 DASHSCOPE_API_KEY。\n"
                "  Windows PowerShell:  $env:DASHSCOPE_API_KEY=\"your-key\"\n"
                "  Linux / macOS:       export DASHSCOPE_API_KEY=\"your-key\""
            )
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        )

        # 预加载提示词模板
        self.prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> str:
        """从外部文件加载系统提示词"""
        if not os.path.exists(self.prompt_path):
            raise FileNotFoundError(
                f"[Engine Error] 致命错误：找不到意图解析提示词文件 '{self.prompt_path}'。"
            )
        with open(self.prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    def _build_zone_mapping(self) -> str:
        """抽取轻量级目标目录 (Entity Catalogue)"""
        if not os.path.exists(self.db_path):
            print(f"[警告] 数据库文件 {self.db_path} 不存在，实体链接将降级。")
            return "[]"

        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            mapping = [{"id": z["zone_id"], "name": z["name"], "aliases": z.get("aliases", [])}
                       for z in data.get("mission_zones", [])]
            return json.dumps(mapping, ensure_ascii=False)
        except Exception as e:
            print(f"[Engine Error] 数据库映射构建失败: {e}")
            return "[]"

    def _call_llm(self, system_prompt: str, user_input: str, mock: bool = False) -> str:
        """大模型 API 真实调用层"""
        if mock:
            return """
            [
              {"intent": "chat", "action": "none", "target": "none", "原始语段": "早上好，"},
              {"intent": "command", "action": "侦察", "target": "ZONE-01", "原始语段": "先侦察1号区域，"},
              {"intent": "command", "action": "打击", "target": "ZONE-02", "原始语段": "再打击二号区域，"},
              {"intent": "command", "action": "打击", "target": "UNKNOWN_ZONE", "原始语段": "最后轰炸99号阵地。"}
            ]
            """

        try:
            # 真实调用 Qwen 模型
            response = self.client.chat.completions.create(
                model="qwen-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input}
                ],
                # 注意：因为我们要求模型输出 JSON Array [...]，
                # 而部分 API 的 json_object 模式强制要求输出 Dict {...}，
                # 为了防止冲突，这里不使用 response_format，依赖 temperature=0 和正则清洗。
                temperature=0.0
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"❌ 意图提取模型调用失败: {e}")
            return ""

    def parse(self, user_input: str, mock: bool = False) -> list:
        """
        执行意图解析的核心 Pipeline
        """
        if not user_input.strip():
            return []

        # 1. 获取实体字典并注入 Prompt
        zone_mapping_json = self._build_zone_mapping()
        system_prompt = self.prompt_template.replace("{zone_mapping_json}", zone_mapping_json)

        # 2. 调用 Qwen 模型
        raw_response = self._call_llm(system_prompt=system_prompt, user_input=user_input, mock=mock)

        if not raw_response:
            return [{"intent": "query", "action": "none", "target": "none", "原始语段": user_input}]

        # 3. 清洗 Markdown 污染 (动态生成反引号防止渲染器转义冲突)
        backticks = "`" * 3
        pattern = rf'^{backticks}(?:json)?\n?|{backticks}$'
        clean_json_str = re.sub(pattern, '', raw_response.strip(), flags=re.MULTILINE).strip()

        # 4. 反序列化与容错处理
        try:
            tasks = json.loads(clean_json_str)
            if not isinstance(tasks, list):
                raise ValueError("模型输出的不是 JSON 数组 (List)")
            return tasks

        except (json.JSONDecodeError, ValueError) as e:
            print(f"[Engine Error] NLU 解析输出非合法 JSON 数组: {e}\nRaw Response: {raw_response}")
            # 降级处理
            return [{
                "intent": "chat",
                "action": "none",
                "target": "none",
                "原始语段": user_input
            }]

# ==========================================
# 本地联调测试入口
# ==========================================
if __name__ == "__main__":
    os.makedirs("./prompt", exist_ok=True)
    prompt_file = "./prompts/intent_model.md"

    if not os.path.exists(prompt_file):
        print(f"⚠️ 请先在 {prompt_file} 创建提示词文件！")
    else:
        # 初始化解析器
        parser = IntentParser(db_path="database.json", prompt_path=prompt_file)

        test_input = "早上好。"
        print(f"{'='*40}\nUser Input:\n{test_input}\n{'='*40}")

        # ⚠️ 注意：此处 mock=False，将直接消耗你的 DashScope Token 进行真实测试
        parsed_tasks = parser.parse(test_input, mock=False)

        print("\n[AST Output]:")
        print(json.dumps(parsed_tasks, indent=2, ensure_ascii=False))
