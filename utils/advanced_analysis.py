# [file name]: advanced_analysis.py
# [file content begin]
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from models import db, SummaryTask, EmailRecord, TaskResponse, Teacher
from collections import Counter, defaultdict
import json
from sqlalchemy import text, func, case

class AdvancedAnalysis:
    def __init__(self):
        pass
    
    def get_reply_trend_analysis(self, task_id):
        """回复趋势分析"""
        try:
            task = SummaryTask.query.get(task_id)
            if not task:
                return None
            
            # 获取所有邮件记录
            records = EmailRecord.query.filter_by(task_id=task_id).all()
            
            if not records:
                return None
            
            # 按日期统计回复情况
            date_stats = defaultdict(lambda: {'total': 0, 'replied': 0})
            
            for record in records:
                if record.sent_time:
                    date_key = record.sent_time.date().isoformat()
                    date_stats[date_key]['total'] += 1
                    if record.status == '已回复':
                        date_stats[date_key]['replied'] += 1
            
            # 转换为时间序列数据
            dates = sorted(date_stats.keys())
            total_series = [date_stats[date]['total'] for date in dates]
            replied_series = [date_stats[date]['replied'] for date in dates]
            reply_rate_series = [
                round((replied / total * 100), 2) if total > 0 else 0 
                for replied, total in zip(replied_series, total_series)
            ]
            
            return {
                'dates': dates,
                'total': total_series,
                'replied': replied_series,
                'reply_rate': reply_rate_series
            }
            
        except Exception as e:
            print(f"回复趋势分析失败: {str(e)}")
            return None
    
    def get_department_analysis(self, task_id):
        """部门分析"""
        try:
            task = SummaryTask.query.get(task_id)
            if not task:
                return None
            
            # 获取各部门的回复情况
            department_stats = {}
            
            # 使用 SQLAlchemy 查询构建器
            department_stats_query = db.session.query(
                EmailRecord.department,
                func.count(EmailRecord.record_id).label('total'),
                func.sum(
                    case(
                        (EmailRecord.status == '已回复', 1),
                        else_=0
                    )
                ).label('replied')
            ).filter(
                EmailRecord.task_id == task_id
            ).group_by(
                EmailRecord.department
            ).all()
            
            for dept, total, replied in department_stats_query:
                reply_rate = round((replied / total * 100), 2) if total > 0 else 0
                department_stats[dept] = {
                    'total': total,
                    'replied': replied,
                    'not_replied': total - replied,
                    'reply_rate': reply_rate
                }
            
            return department_stats if department_stats else None
            
        except Exception as e:
            print(f"部门分析失败: {str(e)}")
            return None
    
    def get_field_analysis(self, task_id):
        """字段分析"""
        try:
            task = SummaryTask.query.get(task_id)
            if not task:
                return None
            
            template_fields = task.get_template_fields()
            if not template_fields:
                print("任务没有模板字段")
                return None
            
            field_stats = {}
            
            for field in template_fields:
                field_name = field['name']
                
                # 统计该字段的填写情况
                field_stats_query = db.session.query(
                    func.count(TaskResponse.response_id).label('total_responses'),
                    func.sum(
                        case(
                            (
                                (TaskResponse.field_value.isnot(None)) & 
                                (TaskResponse.field_value != ''),
                                1
                            ),
                            else_=0
                        )
                    ).label('filled')
                ).join(
                    EmailRecord, TaskResponse.record_id == EmailRecord.record_id
                ).filter(
                    EmailRecord.task_id == task_id,
                    TaskResponse.field_name == field_name
                ).first()
                
                if field_stats_query:
                    total = field_stats_query.total_responses
                    filled = field_stats_query.filled or 0
                    fill_rate = round((filled / total * 100), 2) if total > 0 else 0
                    
                    field_stats[field_name] = {
                        'total': total,
                        'filled': filled,
                        'empty': total - filled,
                        'fill_rate': fill_rate,
                        'required': field.get('required', False)
                    }
            
            return field_stats if field_stats else None
            
        except Exception as e:
            print(f"字段分析失败: {str(e)}")
            return None
    
    def get_response_time_analysis(self, task_id):
        """回复时间分析"""
        try:
            task = SummaryTask.query.get(task_id)
            if not task:
                return None
            
            # 获取已回复的记录及其回复时间
            replied_records = EmailRecord.query.filter_by(
                task_id=task_id, 
                status='已回复'
            ).filter(
                EmailRecord.replied_time.isnot(None),
                EmailRecord.sent_time.isnot(None)
            ).all()
            
            if not replied_records:
                print("没有找到有效的回复时间数据")
                return None
            
            # 计算回复时间（小时）
            response_times = []
            for record in replied_records:
                if record.sent_time and record.replied_time:
                    time_diff = record.replied_time - record.sent_time
                    hours = time_diff.total_seconds() / 3600
                    response_times.append(hours)
            
            if not response_times:
                print("无法计算回复时间")
                return None
            
            # 统计指标
            response_times_array = np.array(response_times)
            
            return {
                'count': len(response_times),
                'mean': round(float(np.mean(response_times_array)), 2),
                'median': round(float(np.median(response_times_array)), 2),
                'min': round(float(np.min(response_times_array)), 2),
                'max': round(float(np.max(response_times_array)), 2),
                'std': round(float(np.std(response_times_array)), 2),
                'percentile_25': round(float(np.percentile(response_times_array, 25)), 2),
                'percentile_75': round(float(np.percentile(response_times_array, 75)), 2),
                'histogram': self._create_histogram(response_times)
            }
            
        except Exception as e:
            print(f"回复时间分析失败: {str(e)}")
            return None
    
    def _create_histogram(self, data, bins=10):
        """创建直方图数据"""
        try:
            hist, bin_edges = np.histogram(data, bins=bins)
            return {
                'counts': hist.tolist(),
                'bins': bin_edges.tolist()
            }
        except Exception as e:
            print(f"创建直方图失败: {str(e)}")
            return {'counts': [], 'bins': []}
    
    def get_comprehensive_analysis(self, task_id):
        """综合分析报告"""
        try:
            task = SummaryTask.query.get(task_id)
            if not task:
                print(f"任务 {task_id} 不存在")
                return None
            
            print(f"开始综合分析任务: {task.task_name}")
            
            # 基础统计
            total_records = EmailRecord.query.filter_by(task_id=task_id).count()
            replied_records = EmailRecord.query.filter_by(task_id=task_id, status='已回复').count()
            reply_rate = round((replied_records / total_records * 100), 2) if total_records > 0 else 0
            
            print(f"基础统计 - 总记录: {total_records}, 已回复: {replied_records}, 回复率: {reply_rate}%")
            
            # 获取各种分析数据
            trend_data = self.get_reply_trend_analysis(task_id)
            print(f"趋势分析: {'成功' if trend_data else '无数据'}")
            
            department_data = self.get_department_analysis(task_id)
            print(f"部门分析: {'成功' if department_data else '无数据'}")
            
            field_data = self.get_field_analysis(task_id)
            print(f"字段分析: {'成功' if field_data else '无数据'}")
            
            time_data = self.get_response_time_analysis(task_id)
            print(f"时间分析: {'成功' if time_data else '无数据'}")
            
            # 生成分析报告
            analysis_report = {
                'task_info': {
                    'task_name': task.task_name,
                    'create_time': task.create_time.isoformat() if task.create_time else None,
                    'deadline': task.deadline.isoformat() if task.deadline else None
                },
                'basic_stats': {
                    'total_teachers': total_records,
                    'replied_teachers': replied_records,
                    'not_replied_teachers': total_records - replied_records,
                    'reply_rate': reply_rate
                },
                'trend_analysis': trend_data,
                'department_analysis': department_data,
                'field_analysis': field_data,
                'time_analysis': time_data,
                'generated_at': datetime.now().isoformat()
            }
            
            print("综合分析完成")
            return analysis_report
            
        except Exception as e:
            print(f"综合分析失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

# 创建全局实例
advanced_analysis = AdvancedAnalysis()
# [file content end]