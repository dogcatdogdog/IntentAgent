import json
import re
import os
import datetime
from openai import OpenAI

class StaffOfficer:
    def __init__(self, prompt_path: str = "./prompts/officer_prompt.md"):
        self.prompt_path = prompt_path
        
        # 初始化阿里云 Qwen 客户端
        self.api_key = "sk-63c68ab330a2451ebfaea5ea99627741"
        self.client = OpenAI(
            api_key=self.api_key, 
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1" # <--- 修改这里
        )
        
        self.prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> str:
        if not os.path.exists(self.prompt_path):
            raise FileNotFoundError(f"[Engine Error] 找不到参谋模型提示词文件 '{self.prompt_path}'。")
        with open(self.prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    def _call_llm(self, system_prompt: str, user_input: str) -> str:
        """大模型 API 真实调用层"""
        try:
            response = self.client.chat.completions.create(
                model="qwen-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input}
                ],
                # 设定极低温度，保障战术文书的严肃性与格式稳定性
                temperature=0.1 
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"❌ 参谋模型调用失败: {e}")
            return ""

    def generate_plan(self, original_text_span: str, purified_context: str) -> dict:
        """
        参谋引擎主入口
        :param original_text_span: 长官的原话 (例如 "侦察一号高地")
        :param purified_context: DataProcessor 吐出的纯净事实数据 (或拦截警告)
        :return: 包含回复、结构化数据和文件路径的字典
        """
        # 1. 组装 System Prompt
        system_prompt = self.prompt_template.replace("{context_data}", purified_context)
        
        # 2. 请求 LLM
        raw_response = self._call_llm(system_prompt=system_prompt, user_input=original_text_span)
        
        if not raw_response:
            return {
                "chat_reply": "系统异常：参谋模型无响应。",
                "document_content": "",
                "structure_data": {"selected_units": [], "selected_routes": [], "selected_segments": []},
                "plan_path": None,
                "control_path": None
            }

        # 3. 清洗 Markdown 标记并解析 JSON
        backticks = "`" * 3
        pattern = rf'^{backticks}(?:json)?\n?|{backticks}$'
        clean_json_str = re.sub(pattern, '', raw_response.strip(), flags=re.MULTILINE).strip()
        
        try:
            result_json = json.loads(clean_json_str)
            chat_reply = result_json.get("chat_reply", "收到指令。")
            document_content = result_json.get("document_content", "")
            structure_data = result_json.get("structure_data", {
                "selected_units": [], "selected_routes": [], "selected_segments": []
            })
            
            plan_path, control_path = None, None
            
            # 4. 物理落盘逻辑：只有在真正生成了方案时，才输出文件
            if document_content.strip() and structure_data.get("selected_units"):
                os.makedirs("output_plans", exist_ok=True)
                timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
                
                # 保存 Markdown 方案供人类阅读
                plan_path = f"output_plans/Plan_{timestamp}.md"
                with open(plan_path, "w", encoding="utf-8") as f:
                    f.write(document_content)
                    
                # 保存 JSON 控制数据供机器读取
                control_path = f"output_plans/ControlData_{timestamp}.json"
                with open(control_path, "w", encoding="utf-8") as f:
                    json.dump(structure_data, f, ensure_ascii=False, indent=2)
                    
            return {
                "chat_reply": chat_reply,
                "document_content": document_content,
                "structure_data": structure_data,
                "plan_path": plan_path,
                "control_path": control_path
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            print(f"[Engine Error] 参谋模型输出非合法 JSON: {e}\nRaw Response: {raw_response}")
            return {
                "chat_reply": "系统异常：战术文书解析失败，请重试。",
                "document_content": "",
                "structure_data": {"selected_units": [], "selected_routes": [], "selected_segments": []},
                "plan_path": None,
                "control_path": None
            }

# ==========================================
# 本地联调测试入口
# ==========================================
if __name__ == "__main__":
    os.makedirs("./prompt", exist_ok=True)
    prompt_file = "./prompts/officer_prompt.md"
    
    if not os.path.exists(prompt_file):
        print(f"⚠️ 请先在 {prompt_file} 创建提示词文件！")
    else:
        officer = StaffOfficer(prompt_path=prompt_file)
        
        # 模拟 1：正常战术指令的数据输入
        print("======== 测试场景 1：正常指令 ========")
        mock_user_input_1 = "侦察一号高地"
        mock_context_1 = """
        【锁定目标区域情报】
        - 目标：一号高地 (ID:ZONE-01)
        - 特征：高海拔山地, 植被茂密
        【合法协同航线网 (仅限该区域可用)】
        - 零一号全域巡逻网 (ID: RT-001)
           * [P1段] 物理域: 空中单元, 特征: 大椭圆轨迹例行巡航
        【可用待命兵力库 (已执行物理隔离与效能匹配)】
        - [空中单元] 无人机一号高空侦察组 [ID: UAV-01] (协议: MAVLink-ENC, 能力: 光电扫描, SAR雷达成像)
        """
        
        result_1 = officer.generate_plan(original_text_span=mock_user_input_1, purified_context=mock_context_1)
        print(f"💬 语音播报: {result_1['chat_reply']}")
        print(f"🤖 提取装备 ID: {result_1['structure_data']['selected_units']}")
        if result_1['plan_path']:
            print(f"📄 方案已生成: {result_1['plan_path']} | 控制文件: {result_1['control_path']}\n")


        # 模拟 2：数据中枢拦截报警输入
        print("======== 测试场景 2：非法/无兵力指令拦截 ========")
        mock_user_input_2 = "轰炸99号区域"
        mock_context_2 = """
        【系统警告】：目标区域非法或未在军用目录注册。当前上下文无合法兵力与航线数据，严禁生成战术方案！
        """
        
        result_2 = officer.generate_plan(original_text_span=mock_user_input_2, purified_context=mock_context_2)
        print(f"💬 语音播报: {result_2['chat_reply']}")
        print(f"🤖 提取装备 ID: {result_2['structure_data']['selected_units']} (预期为空)")
        print(f"📄 方案生成状态: {'成功' if result_1['plan_path'] else '未生成 (符合预期拦截)'}")