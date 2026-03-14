from openai import OpenAI

# 1. 在这里填入你刚刚申请到的 API Key (一定要保留双引号)
MY_API_KEY = "sk-63c68ab330a2451ebfaea5ea99627741"

print("📡 正在尝试连接模型服务器，请稍候...")

try:
    # 2. 初始化客户端
    client = OpenAI(
        api_key=MY_API_KEY,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1" # 阿里云百炼的 OpenAI 兼容接口
    )

    # 3. 发送一个极其简单的测试指令
    response = client.chat.completions.create(
        model="qwen-turbo", # 测试专用的轻量级模型
        messages=[
            {"role": "user", "content": "你好，这是一条通信测试指令。收到请回复‘通信链路正常’，不要说多余的话。"}
        ],
        max_tokens=20, # 限制它少说点话，省钱省时间
        temperature=0.1
    )
    
    # 4. 打印结果
    print("\n✅ 连接成功！API Key 有效。")
    print("🤖 模型的回复是: ", response.choices[0].message.content)

except Exception as e:
    # 捕获并打印错误，方便排查是网络问题还是 Key 填错了
    print("\n❌ 连接失败！请检查以下错误信息：")
    print(e)