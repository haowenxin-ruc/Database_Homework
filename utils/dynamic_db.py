# [file name]: utils/dynamic_db.py
from models import db
from sqlalchemy import text
import re

class DynamicDBManager:
    @staticmethod
    def get_table_name(task_id):
        """生成唯一的表名"""
        return f"task_data_{task_id}"

    @staticmethod
    def sanitize_column_name(name):
        """清洗列名，防止SQL注入，并将特殊字符转换为下划线"""
        # 将非字母数字的字符替换为下划线，保留中文
        clean_name = re.sub(r'[^\w\u4e00-\u9fa5]', '_', name)
        # 避免数字开头
        if clean_name[0].isdigit():
            clean_name = f"col_{clean_name}"
        return clean_name

    @staticmethod
    def create_task_table(task_id, template_fields):
        """
        根据任务ID和模板字段，动态创建一张物理表
        """
        table_name = DynamicDBManager.get_table_name(task_id)
        
        # 1. 基础字段 (用于关联和元数据)
        columns_sql = [
            "id INTEGER PRIMARY KEY AUTOINCREMENT",
            "teacher_id INTEGER",
            "teacher_name TEXT",
            "department TEXT",
            "email TEXT",
            "reply_time DATETIME"
        ]
        
        # 2. 动态字段 (来自Excel模板)
        # 记录原始列名到清洗后列名的映射，以便后续插入数据
        column_mapping = {}
        
        for field in template_fields:
            original_name = field['name']
            safe_name = DynamicDBManager.sanitize_column_name(original_name)
            
            # 防止列名重复
            if safe_name in ['id', 'teacher_id', 'teacher_name', 'department', 'email', 'reply_time']:
                safe_name = f"field_{safe_name}"
            
            # 默认全部使用 TEXT 类型，因为Excel数据类型不确定
            columns_sql.append(f"'{safe_name}' TEXT") 
            column_mapping[original_name] = safe_name

        # 3. 执行建表语句
        create_sql = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            {', '.join(columns_sql)}
        );
        """
        
        try:
            db.session.execute(text(create_sql))
            db.session.commit()
            print(f"✅ 动态表 {table_name} 创建成功")
            return True, column_mapping
        except Exception as e:
            db.session.rollback()
            print(f"❌ 动态表创建失败: {str(e)}")
            return False, str(e)

    @staticmethod
    def save_response(task_id, teacher_info, response_data, column_mapping):
        """
        将回复数据保存到动态表中
        teacher_info: dict, 包含 teacher_id, name, dept, email
        response_data: dict, Excel解析出来的原始数据 { '经费': '100', ... }
        column_mapping: dict, 原始列名 -> 数据库列名
        """
        table_name = DynamicDBManager.get_table_name(task_id)
        
        # 1. 先删除旧数据 (如果该教师已回复过)，实现覆盖更新
        delete_sql = f"DELETE FROM {table_name} WHERE teacher_id = :tid"
        db.session.execute(text(delete_sql), {'tid': teacher_info['teacher_id']})
        
        # 2. 构建插入语句
        # 基础字段
        cols = ['teacher_id', 'teacher_name', 'department', 'email', 'reply_time']
        vals = {
            'teacher_id': teacher_info['teacher_id'],
            'teacher_name': teacher_info['teacher_name'],
            'department': teacher_info['department'],
            'email': teacher_info['email'],
            'reply_time': teacher_info['reply_time']
        }
        
        # 动态字段
        for original_key, value in response_data.items():
            if original_key in column_mapping:
                safe_col = column_mapping[original_key]
                cols.append(f"'{safe_col}'") # 列名加引号防止关键字冲突
                # 参数化查询的key
                param_key = f"v_{safe_col}"
                vals[param_key] = str(value) if value is not None else ''
        
        # 构造 SQL: INSERT INTO table (c1, c2) VALUES (:v1, :v2)
        placeholders = [f":{k}" if k in ['teacher_id', 'teacher_name', 'department', 'email', 'reply_time'] 
                        else f":v_{k.strip(chr(39))}" for k in cols]
        
        insert_sql = f"""
        INSERT INTO {table_name} ({', '.join(cols)}) 
        VALUES ({', '.join(placeholders)})
        """
        
        try:
            db.session.execute(text(insert_sql), vals)
            db.session.commit()
            print(f"✅ 数据已同步到动态表 {table_name}")
            return True
        except Exception as e:
            db.session.rollback()
            print(f"❌ 同步动态表失败: {str(e)}")
            # 打印调试信息
            print(f"SQL: {insert_sql}")
            print(f"Params: {vals}")
            return False

# 创建全局实例 (可选)
dynamic_db = DynamicDBManager()