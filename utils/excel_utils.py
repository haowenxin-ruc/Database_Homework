import pandas as pd
import openpyxl
from openpyxl import Workbook
import os

def create_template_from_fields(fields, output_path):
    """根据字段列表创建Excel模板"""
    wb = Workbook()
    ws = wb.active
    ws.title = "数据填写表"
    
    # 添加表头
    headers = [field['name'] for field in fields]
    ws.append(headers)
    
    # 设置列宽
    for col, header in enumerate(headers, 1):
        column_letter = openpyxl.utils.get_column_letter(col)
        ws.column_dimensions[column_letter].width = 15
    
    # 保存文件
    wb.save(output_path)
    return output_path

def parse_excel_template(template_path):
    """解析Excel模板，提取字段信息"""
    try:
        df = pd.read_excel(template_path, nrows=1)  # 只读取第一行
        fields = []
        for col in df.columns:
            fields.append({
                'name': col,
                'type': 'string',  # 默认类型
                'required': False  # 默认非必填
            })
        return fields
    except Exception as e:
        print(f"解析Excel模板失败：{str(e)}")
        return []

def parse_reply_excel(file_data, task_fields):
    """解析回复的Excel文件数据"""
    try:
        # 将文件数据保存为临时文件
        temp_path = f"temp_reply_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
        with open(temp_path, 'wb') as f:
            f.write(file_data)
        
        # 读取Excel文件
        df = pd.read_excel(temp_path)
        print(f"解析到 {len(df)} 行数据")
        
        # 提取数据（假设只有一行有效数据）
        if len(df) > 0:
            row_data = df.iloc[0].to_dict()
            print(f"提取的数据: {row_data}")
            
            # 清理数据，只保留模板中定义的字段
            cleaned_data = {}
            template_field_names = [field['name'] for field in task_fields]
            
            for field_name, value in row_data.items():
                if field_name in template_field_names and pd.notna(value):
                    cleaned_data[field_name] = str(value)
            
            # 删除临时文件
            os.remove(temp_path)
            
            return cleaned_data
        else:
            os.remove(temp_path)
            return {}
            
    except Exception as e:
        print(f"解析回复Excel失败：{str(e)}")
        # 确保删除临时文件
        try:
            os.remove(temp_path)
        except:
            pass
        return {}

def merge_excel_files(file_paths, output_path):
    """合并多个Excel文件"""
    try:
        all_data = []
        for file_path in file_paths:
            df = pd.read_excel(file_path)
            all_data.append(df)
        
        merged_df = pd.concat(all_data, ignore_index=True)
        merged_df.to_excel(output_path, index=False)
        return True
    except Exception as e:
        print(f"合并Excel文件失败：{str(e)}")
        return False

# 添加datetime导入
from datetime import datetime