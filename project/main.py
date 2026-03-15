import json
import time
from intent_model import IntentParser
from data_processor_v2 import process_task
from staff_officer import StaffOfficer

def main():
    print("🚀 [系统启动] 正在初始化空海地一体化指挥中枢...\n")
    
    try:
        # 1. 初始化两大大模型引擎 (请确保 prompt 文件路径正确)
        intent_parser = IntentParser(db_path="database.json", prompt_path="./prompts/intent_model.md")
        staff_officer = StaffOfficer(prompt_path="./prompts/officer_prompt.md")
    except Exception as e:
        print(f"❌ 引擎初始化失败，请检查提示词文件路径是否正确: {e}")
        return
        
    print("✅ [系统启动] 引擎初始化完成，全域数据总线已连接。\n")
    print("=" * 70)
    
    # 模拟长官下达的极限复合指令 (包含：日常打招呼 + 合法侦察指令 + 非法打击指令)
    test_cases = [
        # 测试用例 1：简单单域指令 (测试基本解析与侦察闭环)
        "前往一号高地执行战略侦察。",
        
        # 测试用例 2：复杂跨域立体打击 (测试兵力过滤与复杂航线 RT-004)
        # ⚠️预期：UAV-02 状态为 Deployed 会被过滤，实际出动的应该是 USV-03 和 UGV-02
        "对三号近岸枢纽发起立体打击，彻底端了它！",
        
        # 测试用例 3：极端环境封控与电子战 (测试多域协同与电磁压制)
        "全面封锁五号城市废墟，注意那里有强电磁干扰和反坦克雷区。",
        
        # 测试用例 4：物理域与可用兵力冲突 (测试 DataProcessor 的硬拦截)
        # ⚠️预期：4号山谷是内陆峡谷，不可能有水面航线，USV 无法进入，且打击兵力可能不足，应触发拦截。
        "派无人船去四号隐蔽山谷进行打击。",
        
        # 测试用例 5：非法坐标防线测试 (测试未知目标的安全垫)
        "立刻轰炸九十九号坐标点。",
        
        # 测试用例 6：复合意图与全局查询 (测试时序拆分与 Query 状态)
        "长官好，先派警戒船去封控二号海湾，然后再查一下我们还有多少能用的空中单元？",
        "去给我买杯水"
    ]

    print(f"🚀 [系统启动] 载入测试集，共 {len(test_cases)} 条极限测试用例...\n")
    print("=" * 70)

    for i, user_input in enumerate(test_cases):
        print(f"\n\n🔶 【TEST CASE {i+1}】 🎙️ [长官原话]: {user_input}")
        print("-" * 70)
        
        # --- 第一跳：意图解析 ---
        start_time = time.time()
        tasks = intent_parser.parse(user_input, mock=False)
        if not tasks:
            print("⚠️ 意图解析失败。")
            continue
            
        print(f"🧩 [解析完毕] 耗时 {time.time()-start_time:.2f}s。拆分为 {len(tasks)} 个子任务。")
        
        # --- 第二 & 第三跳：数据检验与方案生成 ---
        for idx, task in enumerate(tasks):
            print(f"\n   ▶️ [子任务 {idx+1}/{len(tasks)}] 意图: {task['intent']} | 动作: {task['action']} | 目标: {task['target']}")
            
            data_result = process_task(task)
            status = data_result.get("status")
            context_text = data_result.get("context_text")
            print("数据处理结果:",context_text)
            
            if status == "error":
                print(f"   ❌ [系统异常] 数据中枢崩溃: {context_text}")
                continue
                
            plan_result = staff_officer.generate_plan(
                original_text_span=task.get("原始语段", ""),
                purified_context=context_text
            )
            
            print(f"   💬 [语音播报]: {plan_result.get('chat_reply')}")
            
            if plan_result.get("plan_path"):
                print(f"   📄 [下发作战方案]: {plan_result.get('plan_path')}")
                print(f"   🤖 [提取的控制 ID]: {json.dumps(plan_result.get('structure_data'), ensure_ascii=False)}")
            elif status == "intercepted":
                print(f"   🛡️ [系统拦截]: 缺乏执行条件。")
            elif status == "passthrough":
                print(f"   ☕ [闲聊待机]: 无战术生成。")
            elif status == "success" and task["intent"] == "query":
                print(f"   📊 [态势查询]: 摘要已生成。")
            
    print("\n" + "=" * 70)
    print("✅ [总控完毕] 复合指令全链路调度执行完成。")

if __name__ == "__main__":
    main()