# [file name]: utils/ai_utils.py
from openai import OpenAI
from config import config
from models import db, SummaryTask
from sqlalchemy import text
import re

class AIService:
    def __init__(self):
        self.client = OpenAI(
            api_key=config.AI_API_KEY,
            base_url=config.AI_BASE_URL
        )

    def generate_and_execute_sql(self, task_id, messages_history):
        """
        支持上下文记忆的 SQL 生成
        :param task_id: 任务ID
        :param messages_history: 前端传来的对话历史List [{'role':'user', 'content':'...'}, ...]
        """
        # 1. 获取Schema
        task = SummaryTask.query.get(task_id)
        if not task: return False, "任务不存在"
            
        table_name = f"task_data_{task_id}"
        col_mapping = task.get_column_mapping()
        
        # 2. 构造系统提示词 (System Prompt) - 这是 AI 的灵魂，必须放在第一条
        schema_desc = f"Table Name: {table_name}\nColumns:\n"
        schema_desc += "- teacher_name (教师姓名)\n- department (所在系)\n- email (邮箱)\n"
        for excel_col, db_col in col_mapping.items():
            schema_desc += f"- {db_col} (含义: {excel_col})\n"

        system_prompt = {
            "role": "system", 
            "content": f"""
            你是一个 SQLite 数据分析专家。
            【表结构】
            {schema_desc}
            
            【规则】
            1. 根据用户的历史对话和最新问题，生成 SQL。
            2. 只返回 SQL 语句，不要 Markdown，不要 ```sql``` 包裹。
            3. 只能用 SELECT。
            4. 如果用户的问题模糊，请根据历史上下文推断。
            """
        }

        # 3. 组合完整的请求消息：[System Prompt] + [历史对话]
        # 历史对话已经包含了用户的最新问题
        full_messages = [system_prompt] + messages_history

        # 4. 调用大模型
        try:
            print(f"🤖 AI 正在思考... (上下文长度: {len(full_messages)})")
            
            response = self.client.chat.completions.create(
                model=config.AI_MODEL_NAME,
                messages=full_messages,
                temperature=0.1
            )
            
            sql = response.choices[0].message.content.strip()
            # 清理 Markdown
            sql = re.sub(r'^```sql|```$', '', sql).strip()
            # 有时候 AI 会忍不住说话，只提取 SQL 部分
            if "SELECT" in sql.upper():
                # 简单的提取逻辑，防止 AI 说 "Here is the SQL: SELECT..."
                match = re.search(r'(SELECT[\s\S]+)', sql, re.IGNORECASE)
                if match: sql = match.group(1)
            
            print(f"💻 生成 SQL: {sql}")
            
            # 5. 执行 SQL
            result_proxy = db.session.execute(text(sql))
            columns = result_proxy.keys()
            results = [dict(zip(columns, row)) for row in result_proxy.fetchall()]
            
            return True, {
                "sql": sql,
                "count": len(results),
                "data": results,
                "ai_reply": f"已为您查询到 {len(results)} 条结果。" # AI 的文本回复
            }
            
        except Exception as e:
            print(f"❌ AI 错误: {e}")
            return False, str(e)

ai_service = AIService()