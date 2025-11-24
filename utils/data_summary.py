# [file name]: data_summary.py
# [file content begin]
import pandas as pd
import os
from datetime import datetime
from models import db, SummaryTask, EmailRecord, TaskResponse, Teacher
from utils.excel_utils import merge_excel_files

class DataSummary:
    def __init__(self):
        self.export_dir = 'exports'
        os.makedirs(self.export_dir, exist_ok=True)
    
    def generate_task_summary(self, task_id):
        """生成任务汇总表"""
        try:
            task = SummaryTask.query.get(task_id)
            if not task:
                return False, "任务不存在"
            
            # 获取所有已回复的记录
            replied_records = EmailRecord.query.filter_by(
                task_id=task_id, 
                status='已回复'
            ).all()
            
            if not replied_records:
                return False, "暂无回复数据"
            
            # 获取模板字段
            template_fields = task.get_template_fields()
            field_names = [field['name'] for field in template_fields]
            
            # 构建数据列表
            data_rows = []
            for record in replied_records:
                teacher = Teacher.query.get(record.teacher_id)
                if not teacher:
                    continue
                
                # 基础信息
                row_data = {
                    '序号': len(data_rows) + 1,
                    '姓名': teacher.teacher_name,
                    '所在系': teacher.department,
                    '邮箱': teacher.email,
                    '回复时间': record.replied_time.strftime('%Y-%m-%d %H:%M') if record.replied_time else '未知'
                }
                
                # 获取回复的字段数据
                responses = TaskResponse.query.filter_by(record_id=record.record_id).all()
                response_dict = {resp.field_name: resp.field_value for resp in responses}
                
                # 添加模板字段数据
                for field_name in field_names:
                    row_data[field_name] = response_dict.get(field_name, '')
                
                data_rows.append(row_data)
            
            # 创建DataFrame
            df = pd.DataFrame(data_rows)
            
            # 生成文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"汇总_{task.task_name}_{timestamp}.xlsx"
            filepath = os.path.join(self.export_dir, filename)
            
            # 保存Excel文件
            df.to_excel(filepath, index=False, engine='openpyxl')
            
            print(f"✅ 汇总表生成成功: {filename}, 共 {len(data_rows)} 条记录")
            return True, filepath
            
        except Exception as e:
            print(f"❌ 生成汇总表失败: {str(e)}")
            return False, str(e)
    
    def get_summary_statistics(self, task_id):
        """获取汇总统计信息"""
        try:
            task = SummaryTask.query.get(task_id)
            if not task:
                return None
            
            # 基础统计
            total_teachers = EmailRecord.query.filter_by(task_id=task_id).count()
            replied_teachers = EmailRecord.query.filter_by(task_id=task_id, status='已回复').count()
            not_replied_teachers = total_teachers - replied_teachers
            reply_rate = round((replied_teachers / total_teachers * 100), 2) if total_teachers > 0 else 0
            
            # 字段统计
            field_stats = {}
            template_fields = task.get_template_fields()
            
            if template_fields:
                for field in template_fields:
                    field_name = field['name']
                    # 获取该字段的回复情况
                    field_responses = TaskResponse.query.join(
                        EmailRecord, TaskResponse.record_id == EmailRecord.record_id
                    ).filter(
                        EmailRecord.task_id == task_id,
                        EmailRecord.status == '已回复',
                        TaskResponse.field_name == field_name
                    ).all()
                    
                    filled_count = len([r for r in field_responses if r.field_value and r.field_value.strip()])
                    field_stats[field_name] = {
                        'total': len(field_responses),
                        'filled': filled_count,
                        'fill_rate': round((filled_count / len(field_responses) * 100), 2) if field_responses else 0
                    }
            
            return {
                'total_teachers': total_teachers,
                'replied_teachers': replied_teachers,
                'not_replied_teachers': not_replied_teachers,
                'reply_rate': reply_rate,
                'field_stats': field_stats
            }
            
        except Exception as e:
            print(f"❌ 获取统计信息失败: {str(e)}")
            return None
    
    def export_filtered_summary(self, task_id, department_filter=None):
        """导出筛选后的汇总表（按部门筛选）"""
        try:
            task = SummaryTask.query.get(task_id)
            if not task:
                return False, "任务不存在"
            
            # 构建查询
            query = EmailRecord.query.filter_by(task_id=task_id, status='已回复')
            
            if department_filter:
                query = query.filter_by(department=department_filter)
            
            replied_records = query.all()
            
            if not replied_records:
                return False, "暂无符合条件的回复数据"
            
            # 生成汇总表
            return self.generate_task_summary(task_id)
            
        except Exception as e:
            return False, str(e)

# 创建全局实例
data_summary = DataSummary()
# [file content end]