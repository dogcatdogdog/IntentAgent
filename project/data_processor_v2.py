import json
import os

DB_PATH = "database.json"

def _load_database() -> dict:
    """加载本地态势数据库"""
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"[Engine Error] 态势数据库 {DB_PATH} 丢失！")
    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def _get_global_summary() -> str:
    """
    提供给全局查询意图 (query) 的精简态势摘要。
    优化点：将设备按战备状态分级，协助长官一眼识破真实战力。
    """
    try:
        data = _load_database()
        units = data.get("available_units", [])
        standby_units = [u for u in units if u.get('status') == "Standby"]
        unavailable_units = [u for u in units if u.get('status') != "Standby"]

        summary = "【战备态势实时汇总】\n"
        summary += f"💡 随时待命单元 (Standby: {len(standby_units)}个):\n"
        for u in standby_units:
            summary += f"- [{u.get('domain', '未知域')}] {u.get('name', '未知装备')} [ID: {u.get('unit_id', 'N/A')}] ({u.get('sub_function', '')})\n"
            
        summary += f"\n⚠️ 暂不可用单元 ({len(unavailable_units)}个):\n"
        summary += ", ".join([f"{u.get('name', '未知')}({u.get('status', 'N/A')})" for u in unavailable_units])
        
        summary += "\n\n【全局区域清单】\n"
        for zone in data.get("mission_zones", []):
            summary += f"- {zone.get('name', '未知区域')} (ID: {zone.get('zone_id', 'N/A')})\n"
            
        return summary
    except Exception as e:
        return f"【系统警告】态势数据库读取失败: {e}"

def _get_tactical_context(target_id: str, action_type: str) -> dict:
    """
    战术指令核心过滤引擎 (O(1) 哈希查询与物理隔离)
    """
    if target_id == "UNKNOWN_ZONE" or not target_id:
        return {
            "status": "intercepted", 
            "context_text": "【系统警告】：目标区域非法或未在军用目录注册。当前上下文无合法兵力与航线数据，严禁生成战术方案！"
        }

    data = _load_database()
    zones = data.get("mission_zones", [])
    
    # 1. O(1) 精确锁定目标区域
    target_zone = next((z for z in zones if z.get('zone_id') == target_id), None)
    
    if not target_zone:
        return {
            "status": "intercepted", 
            "context_text": f"【系统警告】：数据库中未找到 ID 为 {target_id} 的情报。严禁生成战术方案！"
        }

    # 2. 航线空间物理隔离与域提取
    valid_routes = [
        r for r in data.get("available_routes", [])
        if target_zone["zone_id"] in r.get("applicable_zones", [])
    ]
    
    allowed_domains = set()
    domain_keywords = {
        "空中单元": ["空", "飞行", "高空", "低空"],
        "海面单元": ["水", "海", "潜", "洋流"],
        "突击单元": ["陆", "地", "穿插", "建筑", "山地"]
    }

    for route in valid_routes:
        for seg in route.get("segments", []):
            seg_domain_text = seg.get("domain", "")
            for domain_key, kws in domain_keywords.items():
                if any(k in seg_domain_text for k in kws):
                    allowed_domains.add(domain_key)
    
    # 3. 兵力战术效能硬隔离
    action_capability_mapping = {
        "侦察": ["侦察", "监视", "探测", "测绘", "预警", "侦测", "信号", "感知"],
        "打击": ["打击", "火力", "突击", "毁灭", "压制", "摧毁", "爆破", "反装甲", "自杀"],
        "封控": ["警戒", "封锁", "拦截", "干扰", "压制", "防御", "巡逻", "电子战"]
    }
    allowed_capabilities = action_capability_mapping.get(action_type, [])

    active_units = []
    for unit in data.get("available_units", []):
        is_standby = unit.get("status") == "Standby"
        is_domain_allowed = unit.get("domain") in allowed_domains
        
        # 匹配装备的 profile
        unit_profile = unit.get("sub_function", "") + str(unit.get("capabilities", ""))
        is_capability_allowed = any(cap in unit_profile for cap in allowed_capabilities) if allowed_capabilities else True
        
        if is_standby and is_domain_allowed and is_capability_allowed:
            active_units.append(unit)

    # 4. 组装极致纯净上下文
    context_text = f"【锁定目标区域情报】\n- 目标：{target_zone.get('name', '')} (ID:{target_zone.get('zone_id', '')})\n- 特征：{', '.join(target_zone.get('terrain_features', []))}\n- 战略价值：{target_zone.get('strategic_value', '')}\n\n"
    
    context_text += "【合法协同航线网 (仅限该区域可用)】\n"
    if not valid_routes:
        context_text += "- 警告：该区域目前无可用协同航线段，无法部署任何平台。\n"
    for route in valid_routes:
        context_text += f"- {route.get('route_name', '')} (ID: {route.get('route_id', '')})\n"
        for seg in route.get("segments", []):
            context_text += f"   * [{seg.get('segment_code', '')}段] 物理域: {seg.get('domain', '')}, 特征: {seg.get('feature', '')}\n"

    context_text += "\n【可用待命兵力库 (已执行物理隔离与效能匹配)】\n"
    
    if not active_units:
        context_text += "- 【系统警告】当前任务类型在该区域无匹配的待命兵力，严禁生成方案。\n"
        # ⚠️ 核心逻辑：如果没兵，即便找到了区域，也要把 status 设为 intercepted
        return {"status": "intercepted", "context_text": context_text}
        
    for unit in active_units:
        context_text += f"- [{unit.get('domain', '')}] {unit.get('name', '')} [ID: {unit.get('unit_id', '')}] (协议: {unit.get('protocol', '')}, 能力: {unit.get('capabilities', '')})\n"
        
    return {"status": "success", "context_text": context_text}

def process_task(task: dict) -> dict:
    """
    数据中枢主入口 (Facade Pattern)
    根据 Intent Model 传递的 Task 字典，路由到对应的处理逻辑。
    """
    intent = task.get("intent", "chat")
    action = task.get("action", "none")
    target_id = task.get("target", "none")

    try:
        if intent == "chat":
            return {
                "status": "passthrough",
                "context_text": "【系统状态】：用户选择与你聊天，无战术数据介入。请维持冷酷军人的人设简短回复(比如：早上好，随时待命等)。"
            }
            
        elif intent == "query":
            summary_text = _get_global_summary()
            return {
                "status": "success",
                "context_text": summary_text
            }
            
        elif intent == "command":
            return _get_tactical_context(target_id=target_id, action_type=action)
            
        else:
            return {
                "status": "error",
                "context_text": f"【系统错误】：无法识别的意图类型 '{intent}'。"
            }
            
    except Exception as e:
        return {
            "status": "error",
            "context_text": f"【系统异常】：Data Processor 运行崩溃 - {str(e)}"
        }

# ==========================================
# 本地联调测试入口 (Main Method)
# ==========================================
if __name__ == "__main__":
    # 模拟从 IntentParser 输出的抽象语法树 (AST)
    # 这个数组覆盖了我们的全部核心场景
    mock_tasks_from_intent_model = [
        {"intent": "chat", "action": "none", "target": "none", "原始语段": "早上好，"},
        {"intent": "query", "action": "查询", "target": "none", "原始语段": "我们还有多少可用的无人机？"},
        {"intent": "command", "action": "打击", "target": "UNKNOWN_ZONE", "原始语段": "轰炸99号阵地！"},
        {"intent": "command", "action": "侦察", "target": "ZONE-01", "原始语段": "侦察一号高地。"},
        # 假设 ZONE-02 只有侦察船没有打击船，用来测试“无匹配待命兵力”熔断
        {"intent": "command", "action": "打击", "target": "ZONE-02", "原始语段": "把二号海湾端了。"} 
    ]

    print(f"================ Data Processor 极速管线测试 ================\n")

    for idx, task in enumerate(mock_tasks_from_intent_model):
        print(f"▶️ [Task {idx+1}] 输入: {task['原始语段']}")
        print(f"   参数: intent={task['intent']}, action={task['action']}, target={task['target']}")
        
        # 调用核心处理函数
        result = process_task(task)
        
        # 打印返回的契约结构
        print(f"   [返回 Status] : {result['status']}")
        print(f"   [返回 Context]:\n{'-'*40}\n{result['context_text']}\n{'-'*40}\n")