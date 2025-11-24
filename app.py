# [file name]: app.py
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, send_file
from models import db, Teacher, SummaryTask, EmailRecord, TaskResponse
from config import config
import os
import json
import pandas as pd
from datetime import datetime
from werkzeug.utils import secure_filename
from sqlalchemy import text

# 引入工具类
from utils.email_utils import email_sender
from utils.imap_utils import email_receiver
from utils.excel_utils import parse_reply_excel, parse_excel_template
from utils.data_summary import data_summary
from utils.advanced_analysis import advanced_analysis
from utils.dynamic_db import dynamic_db
from utils.ai_utils import ai_service  # 记得引入
def create_app():
    app = Flask(__name__)
    app.config.from_object(config)
    
    # 初始化数据库
    db.init_app(app)
    
    # 创建必要的目录
    os.makedirs('uploads', exist_ok=True)
    os.makedirs('templates/excel', exist_ok=True)
    os.makedirs('exports', exist_ok=True)

    return app

app = create_app()

# 允许上传的文件类型
ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==========================================
# 1. 页面路由 (View Routes)
# ==========================================

@app.route('/')
def index():
    """首页仪表盘"""
    try:
        teacher_count = Teacher.query.count()
        task_count = SummaryTask.query.count()
        pending_count = EmailRecord.query.filter(EmailRecord.status != '已回复').count()
        completed_count = EmailRecord.query.filter_by(status='已回复').count()
        
        return render_template('index.html',
                             teacher_count=teacher_count,
                             task_count=task_count,
                             pending_count=pending_count,
                             completed_count=completed_count)
    except Exception as e:
        flash(f"加载首页数据失败: {str(e)}")
        return render_template('index.html', teacher_count=0, task_count=0, pending_count=0, completed_count=0)

@app.route('/teachers')
def manage_teachers():
    """教师管理页面渲染路由"""
    try:
        # 获取所有教师，按创建时间倒序排列
        teachers = Teacher.query.order_by(Teacher.created_at.desc()).all()
        return render_template('teachers.html', teachers=teachers)
    except Exception as e:
        print(f"加载教师列表失败: {e}")
        return render_template('teachers.html', teachers=[])

@app.route('/tasks')
def manage_tasks():
    """任务管理页面"""
    try:
        tasks = SummaryTask.query.order_by(SummaryTask.create_time.desc()).all()
        # 获取所有教师，传给前端用于新建任务时的选择
        teachers = Teacher.query.order_by(Teacher.teacher_name).all()
        return render_template('tasks.html', tasks=tasks, teachers=teachers, now=datetime.now())
    except Exception as e:
        print(f"加载任务列表失败: {e}")
        return render_template('tasks.html', tasks=[], teachers=[], now=datetime.now())

@app.route('/tasks/<int:task_id>/summary')
def task_summary(task_id):
    """任务数据汇总页面"""
    try:
        task = SummaryTask.query.get_or_404(task_id)
        stats = data_summary.get_summary_statistics(task_id)
        if not stats:
            stats = {'total_teachers': 0, 'replied_teachers': 0, 'not_replied_teachers': 0, 'reply_rate': 0, 'field_stats': {}}
        return render_template('task_summary.html', task=task, stats=stats)
    except Exception as e:
        flash(f'加载汇总页面失败: {str(e)}')
        return redirect(url_for('manage_tasks'))

@app.route('/tasks/<int:task_id>/replies')
def task_replies(task_id):
    """任务回复状态详情页面"""
    try:
        task = SummaryTask.query.get_or_404(task_id)
        replied_records = EmailRecord.query.filter_by(task_id=task_id, status='已回复').all()
        not_replied_records = EmailRecord.query.filter_by(task_id=task_id, status='未回复').all()
        
        replied_list = []
        for r in replied_records:
            teacher = Teacher.query.get(r.teacher_id)
            if teacher:
                replied_list.append({
                    'teacher_name': teacher.teacher_name,
                    'department': teacher.department,
                    'reply_time': r.replied_time.strftime('%Y-%m-%d %H:%M') if r.replied_time else '未知'
                })

        not_replied_list = []
        for r in not_replied_records:
            teacher = Teacher.query.get(r.teacher_id)
            if teacher:
                not_replied_list.append({'teacher_name': teacher.teacher_name, 'department': teacher.department, 'email': teacher.email})

        total = len(replied_list) + len(not_replied_list)
        stats = {
            'total': total,
            'replied': len(replied_list),
            'not_replied': len(not_replied_list),
            'reply_rate': round((len(replied_list) / total * 100), 2) if total > 0 else 0
        }
        
        return render_template('task_replies.html', task=task, statistics=stats, replied_teachers=replied_list, not_replied_teachers=not_replied_list)
    except Exception as e:
        flash(f'加载回复详情失败: {str(e)}')
        return redirect(url_for('manage_tasks'))

@app.route('/tasks/<int:task_id>/advanced-analysis')
def advanced_analysis_page(task_id):
    """高级分析页面"""
    try:
        task = SummaryTask.query.get_or_404(task_id)
        return render_template('advanced_analysis.html', task=task)
    except Exception as e:
        flash(f'加载高级分析页面失败: {str(e)}')
        return redirect(url_for('task_summary', task_id=task_id))

@app.route('/ai-assistant')

def ai_assistant():
    # 获取所有任务，传给前端做下拉框
    tasks = SummaryTask.query.order_by(SummaryTask.create_time.desc()).all()
    return render_template('ai_assistant.html', tasks=tasks)


# ==========================================
# 2. API 路由 - 教师管理 (Teachers API)
# ==========================================

@app.route('/api/teachers', methods=['POST'])
def add_teacher():
    try:
        data = request.form
        if Teacher.query.filter_by(email=data.get('email')).first():
            return jsonify({'success': False, 'error': '该邮箱已存在，请勿重复添加'})

        teacher = Teacher(
            teacher_name=data.get('teacher_name'),
            department=data.get('department'),
            email=data.get('email'),
            phone=data.get('phone'),
            title=data.get('title')
        )
        db.session.add(teacher)
        db.session.commit()
        return jsonify({'success': True, 'message': '教师添加成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/teachers/import', methods=['POST'])
def import_teachers():
    """批量导入教师"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '未上传文件'})
        file = request.files['file']
        if file.filename == '' or not allowed_file(file.filename):
            return jsonify({'success': False, 'error': '文件无效'})
            
        filename = secure_filename(file.filename)
        filepath = os.path.join('uploads', filename)
        file.save(filepath)
        
        try:
            df = pd.read_csv(filepath) if filename.endswith('.csv') else pd.read_excel(filepath)
            df.columns = df.columns.str.strip()
            
            required_cols = ['姓名', '邮箱', '所在系']
            missing = [c for c in required_cols if c not in df.columns]
            if missing:
                return jsonify({'success': False, 'error': f'缺少列: {", ".join(missing)}'})
            
            success, dupes = 0, 0
            for _, row in df.iterrows():
                email = str(row['邮箱']).strip()
                if Teacher.query.filter_by(email=email).first():
                    dupes += 1
                    continue
                t = Teacher(
                    teacher_name=str(row['姓名']).strip(),
                    email=email,
                    department=str(row['所在系']).strip(),
                    phone=str(row.get('手机', '')).strip() if '手机' in df.columns else None,
                    title=str(row.get('职称', '')).strip() if '职称' in df.columns else None
                )
                db.session.add(t)
                success += 1
            db.session.commit()
            return jsonify({'success': True, 'message': f'成功 {success}，重复跳过 {dupes}'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
        finally:
            if os.path.exists(filepath): os.remove(filepath)
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/teachers/<int:teacher_id>', methods=['DELETE'])
def delete_teacher(teacher_id):
    try:
        teacher = Teacher.query.get_or_404(teacher_id)
        email_records = EmailRecord.query.filter_by(teacher_id=teacher_id).all()
        for record in email_records:
            TaskResponse.query.filter_by(record_id=record.record_id).delete()
            db.session.delete(record)
        db.session.delete(teacher)
        db.session.commit()
        return jsonify({'success': True, 'message': '删除成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/teachers/<int:teacher_id>', methods=['GET'])
def get_teacher_details(teacher_id):
    """获取教师详情 (用于编辑回显)"""
    try:
        teacher = Teacher.query.get_or_404(teacher_id)
        return jsonify({
            'success': True,
            'data': {
                'teacher_id': teacher.teacher_id,
                'teacher_name': teacher.teacher_name,
                'department': teacher.department,
                'email': teacher.email,
                'phone': teacher.phone or '',
                'title': teacher.title or ''
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/teachers/<int:teacher_id>', methods=['POST'])
def update_teacher(teacher_id):
    """更新教师信息 (POST)"""
    try:
        teacher = Teacher.query.get_or_404(teacher_id)
        data = request.form
        print(f"收到更新教师请求 {teacher_id}: {data}") # Debug
        
        new_email = data.get('email')
        
        # 检查邮箱是否被其他教师占用
        existing = Teacher.query.filter_by(email=new_email).first()
        if existing and existing.teacher_id != teacher_id:
            return jsonify({'success': False, 'error': '该邮箱已被其他教师使用'})
            
        # 更新字段
        teacher.teacher_name = data.get('teacher_name')
        teacher.department = data.get('department')
        teacher.email = new_email
        teacher.phone = data.get('phone')
        teacher.title = data.get('title')
        
        db.session.commit()
        return jsonify({'success': True, 'message': '教师信息更新成功'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})


# ==========================================
# 3. API 路由 - 任务管理 (Tasks API)
# ==========================================

@app.route('/api/tasks', methods=['POST'])
def add_task():
    """创建汇总任务 + 动态建表 + 处理选中的教师"""
    try:
        task_name = request.form.get('task_name')
        if SummaryTask.query.filter_by(task_name=task_name).first():
            return jsonify({'success': False, 'error': '任务名称已存在'})

        deadline_str = request.form.get('deadline')
        deadline = datetime.fromisoformat(deadline_str) if deadline_str else None
        
        task = SummaryTask(
            task_name=task_name,
            description=request.form.get('description'),
            deadline=deadline
        )
        
        # 1. 保存任务以获取 task_id
        db.session.add(task)
        db.session.flush()
        
        # 2. 处理模板并建表
        if 'template_file' in request.files:
            file = request.files['template_file']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                save_filename = f"task_{int(datetime.now().timestamp())}_{filename}"
                template_path = os.path.join('templates/excel', save_filename)
                file.save(template_path)
                task.template_path = template_path
                
                # 解析字段
                fields = parse_excel_template(template_path)
                if not fields:
                    db.session.rollback()
                    return jsonify({'success': False, 'error': '模板解析失败'})
                
                task.set_template_fields(fields)
                
                # 动态创建数据库物理表
                success, result = dynamic_db.create_task_table(task.task_id, fields)
                if success:
                    task.set_column_mapping(result)
                else:
                    db.session.rollback()
                    return jsonify({'success': False, 'error': f'动态建表失败: {result}'})
                    
        # 3. 处理选中的教师 (预设发送列表)
        selected_teacher_ids = request.form.getlist('teacher_ids')
        if selected_teacher_ids:
            for tid in selected_teacher_ids:
                teacher = Teacher.query.get(tid)
                if teacher:
                    record = EmailRecord(
                        task_id=task.task_id,
                        teacher_id=teacher.teacher_id,
                        teacher_name=teacher.teacher_name,
                        department=teacher.department,
                        status='未发送' # 初始状态
                    )
                    db.session.add(record)
        
        db.session.commit()
        return jsonify({'success': True, 'message': f'任务创建成功，已分配给 {len(selected_teacher_ids)} 位教师'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    try:
        task = SummaryTask.query.get_or_404(task_id)
        
        # 删除回复详情
        records = EmailRecord.query.filter_by(task_id=task_id).all()
        ids = [r.record_id for r in records]
        if ids:
            TaskResponse.query.filter(TaskResponse.record_id.in_(ids)).delete(synchronize_session=False)
        EmailRecord.query.filter_by(task_id=task_id).delete()
        
        # 删除动态物理表
        table_name = f"task_data_{task_id}"
        try:
            db.session.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
            print(f"已删除物理表: {table_name}")
        except Exception as e:
            print(f"删除物理表失败: {e}")

        db.session.delete(task)
        db.session.commit()
        return jsonify({'success': True, 'message': '删除成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/tasks/<int:task_id>/send-emails', methods=['POST'])
def send_task_emails(task_id):
    """发送任务通知邮件 (只给'未发送'状态的教师)"""
    try:
        task = SummaryTask.query.get_or_404(task_id)
        
        pending_records = EmailRecord.query.filter_by(task_id=task_id, status='未发送').all()
        
        if not pending_records:
            # 兼容处理：如果任务没选人，且没有任何记录
            if EmailRecord.query.filter_by(task_id=task_id).count() == 0:
                return jsonify({'success': False, 'message': '该任务未选择教师，无法发送。请重新创建任务。'})
            return jsonify({'success': True, 'message': '没有待发送的邮件 (所有选定教师已发送)'})

        sent_count = 0
        failed_list = []
        
        for record in pending_records:
            teacher = Teacher.query.get(record.teacher_id)
            if not teacher: continue
            
            subject = f"【请回复】{task.task_name} - 数据汇总工作"
            content = f"""
尊敬的{teacher.teacher_name}老师：

您好！
这是关于“{task.task_name}”的数据收集工作。

任务说明：{task.description or '无'}
截止时间：{task.deadline.strftime('%Y-%m-%d %H:%M') if task.deadline else '未设置'}

请下载附件中的Excel模板，填写相关信息后，直接【回复本邮件】（请保留附件格式）。
系统将自动抓取您的回复。

谢谢配合！
"""
            try:
                if config.MAIL_SERVER:
                    success = email_sender.send_email(teacher.email, subject, content, task.template_path)
                else:
                    print(f"[Dev] 模拟发送给 {teacher.email}")
                    success = True

                if success:
                    record.status = '未回复'
                    record.sent_time = datetime.now()
                    sent_count += 1
                else:
                    failed_list.append(teacher.teacher_name)
                    
            except Exception as e:
                print(f"发送异常: {e}")
                failed_list.append(teacher.teacher_name)
        
        db.session.commit()
        
        msg = f"本次成功发送 {sent_count} 封邮件。"
        if failed_list:
            msg += f" 失败 {len(failed_list)} 人: {', '.join(failed_list[:5])}..."
            
        return jsonify({'success': True, 'message': msg})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f"系统错误: {str(e)}"})

@app.route('/api/tasks/<int:task_id>/remind', methods=['POST'])
def remind_task_emails(task_id):
    """一键催办：给'未回复'的教师发送提醒邮件"""
    try:
        task = SummaryTask.query.get_or_404(task_id)
        
        # 1. 筛选目标：状态为 '未回复' 的记录
        # (注意：'未发送'的是还没发过，'已回复'的不需要催，只有'未回复'的才是由于拖延没交的)
        target_records = EmailRecord.query.filter_by(task_id=task_id, status='未回复').all()
        
        if not target_records:
            return jsonify({'success': True, 'message': '没有需要催办的教师 (大家都回复了，或还没开始发送)'})

        sent_count = 0
        failed_list = []
        
        # 2. 准备催办文案
        subject = f"【温馨提醒】{task.task_name} - 截止临近，请尽快回复"
        
        for record in target_records:
            teacher = Teacher.query.get(record.teacher_id)
            if not teacher: continue
            
            content = f"""
尊敬的{teacher.teacher_name}老师：

您好！
这是一个温馨提醒。关于“{task.task_name}”的数据收集工作即将截止。
系统显示您尚未回复。

截止时间：{task.deadline.strftime('%Y-%m-%d %H:%M') if task.deadline else '未设置'}

烦请您尽快查阅之前的邮件，填写附件中的 Excel 模板并【回复本邮件】。
（如果附件已丢失，请查阅本邮件附件）

如已回复请忽略此邮件。谢谢配合！
"""
            try:
                if config.MAIL_SERVER:
                    # 发送邮件 (带上附件，万一老师把之前的删了)
                    success = email_sender.send_email(
                        to_email=teacher.email,
                        subject=subject,
                        content=content,
                        attachment_path=task.template_path
                    )
                else:
                    print(f"[Dev] 模拟催办: {teacher.email}")
                    success = True

                if success:
                    # 仅更新发送时间，状态保持 '未回复'
                    record.sent_time = datetime.now()
                    sent_count += 1
                else:
                    failed_list.append(teacher.teacher_name)
                    
            except Exception as e:
                print(f"催办异常 {teacher.teacher_name}: {e}")
                failed_list.append(teacher.teacher_name)
        
        db.session.commit()
        
        msg = f"已向 {sent_count} 位未回复的教师发送了提醒。"
        if failed_list:
            msg += f" 发送失败: {', '.join(failed_list[:3])}..."
            
        return jsonify({'success': True, 'message': msg})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/tasks/<int:task_id>/check-replies')
def check_task_replies(task_id):
    """检查回复 + 同步写入动态表"""
    try:
        task = SummaryTask.query.get_or_404(task_id)
        emails = email_receiver.search_reply_emails(task.task_name)
        processed_count = 0
        new_replies = []
        
        col_mapping = task.get_column_mapping()
        
        for email_data in emails:
            teacher = Teacher.query.filter_by(email=email_data['from_email']).first()
            if not teacher: continue
            
            record = EmailRecord.query.filter_by(task_id=task_id, teacher_id=teacher.teacher_id).first()
            
            if not record:
                 record = EmailRecord(task_id=task_id, teacher_id=teacher.teacher_id, 
                                      teacher_name=teacher.teacher_name, department=teacher.department)
                 db.session.add(record)
                 db.session.flush()

            if record.status == '已回复': continue
            
            if email_data['attachments']:
                for att in email_data['attachments']:
                    if att['filename'].lower().endswith(('.xlsx', '.xls')):
                        fields = task.get_template_fields()
                        reply_data = parse_reply_excel(att['data'], fields)
                        
                        if reply_data:
                            # 1. 写入原有 EAV 表
                            for k, v in reply_data.items():
                                db.session.add(TaskResponse(record_id=record.record_id, field_name=k, field_value=v))
                            
                            # 2. 写入动态物理表
                            teacher_info = {
                                'teacher_id': teacher.teacher_id,
                                'teacher_name': teacher.teacher_name,
                                'department': teacher.department,
                                'email': teacher.email,
                                'reply_time': email_data['date']
                            }
                            dynamic_db.save_response(task.task_id, teacher_info, reply_data, col_mapping)
                            
                            record.status = '已回复'
                            record.replied_time = email_data['date']
                            record.reply_title = email_data['subject']
                            new_replies.append({'name': teacher.teacher_name, 'time': str(email_data['date'])})
                            processed_count += 1
                            break
                            
        db.session.commit()
        return jsonify({'success': True, 'message': f'处理 {processed_count} 个新回复', 'new_replies': new_replies})
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/tasks/<int:task_id>/fields')
def get_task_fields(task_id):
    try:
        task = SummaryTask.query.get_or_404(task_id)
        return jsonify({'success': True, 'fields': task.get_template_fields()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/tasks/<int:task_id>/inspect-table', methods=['GET'])
def inspect_task_table(task_id):
    """查看任务对应的动态表结构"""
    try:
        task = SummaryTask.query.get_or_404(task_id)
        table_name = f"task_data_{task_id}"
        mapping = task.get_column_mapping()
        
        try:
            result = db.session.execute(text(f"PRAGMA table_info({table_name})"))
            columns_info = [{'cid': row[0], 'name': row[1], 'type': row[2]} for row in result]
            table_exists = len(columns_info) > 0
        except Exception:
            table_exists = False
            columns_info = []

        sample_data = {}
        if table_exists:
            try:
                row = db.session.execute(text(f"SELECT * FROM {table_name} LIMIT 1")).first()
                if row:
                    for idx, col in enumerate(columns_info):
                        sample_data[col['name']] = row[idx]
            except Exception:
                pass

        return jsonify({
            'success': True,
            'task_name': task.task_name,
            'table_name': table_name,
            'table_exists': table_exists,
            'column_mapping': mapping,
            'physical_columns': columns_info,
            'sample_data': sample_data
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ==========================================
# 4. API 路由 - 数据分析与图表 (Analysis API)
# ==========================================

@app.route('/api/tasks/<int:task_id>/analysis/comprehensive')
def get_comprehensive_analysis(task_id):
    try:
        data = advanced_analysis.get_comprehensive_analysis(task_id)
        if data: return jsonify({'success': True, 'analysis': data})
        return jsonify({'success': False, 'error': '无数据'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ... (trend, department, response-time 接口同理，为节省篇幅已在前面提供，这里确保它们存在) ...
# 为了确保代码完整性，这里补充上这几个短接口
@app.route('/api/tasks/<int:task_id>/analysis/trend')
def get_trend_analysis(task_id):
    data = advanced_analysis.get_reply_trend_analysis(task_id)
    return jsonify({'success': True, 'trend': data} if data else {'success': False, 'error': '无数据'})

@app.route('/api/tasks/<int:task_id>/analysis/department')
def get_department_analysis(task_id):
    data = advanced_analysis.get_department_analysis(task_id)
    return jsonify({'success': True, 'departments': data} if data else {'success': False, 'error': '无数据'})

@app.route('/api/tasks/<int:task_id>/analysis/response-time')
def get_response_time_analysis(task_id):
    data = advanced_analysis.get_response_time_analysis(task_id)
    return jsonify({'success': True, 'time_analysis': data} if data else {'success': False, 'error': '无数据'})

# ==========================================
# 5. API 路由 - 导出与下载与编辑
# ==========================================

@app.route('/api/tasks/<int:task_id>/generate-summary')
def generate_task_summary_file(task_id):
    try:
        success, result = data_summary.generate_task_summary(task_id)
        if success:
            return jsonify({'success': True, 'message': '生成成功', 'download_url': f'/api/download-summary/{os.path.basename(result)}'})
        return jsonify({'success': False, 'error': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/download-summary/<filename>')
def download_summary(filename):
    try:
        file_path = os.path.join('exports', filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True, download_name=filename)
        return jsonify({'success': False, 'error': '文件不存在'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/tasks/<int:task_id>/data-preview')
def get_task_data_preview(task_id):
    """汇总数据预览表格 (含编辑按钮)"""
    try:
        task = SummaryTask.query.get(task_id)
        records = EmailRecord.query.filter_by(task_id=task_id, status='已回复').limit(50).all()
        
        if not records:
            return jsonify({'success': True, 'html': '<div class="text-center p-4 text-muted">暂无回复数据</div>'})
        
        data = []
        fields = task.get_template_fields()
        field_names = [f['name'] for f in fields] if fields else []
        
        for idx, rec in enumerate(records, 1):
            t = Teacher.query.get(rec.teacher_id)
            row = {
                'record_id': rec.record_id, 
                '序号': idx, 
                '姓名': t.teacher_name, 
                '部门': t.department
            }
            responses = TaskResponse.query.filter_by(record_id=rec.record_id).all()
            resp_dict = {r.field_name: r.field_value for r in responses}
            
            for col in (field_names if field_names else list(resp_dict.keys())):
                row[col] = resp_dict.get(col, '')
            data.append(row)
            
        headers = ['序号', '姓名', '部门'] + (field_names if field_names else []) + ['操作']
        html = '<div class="table-responsive"><table class="table table-sm table-striped table-hover align-middle"><thead><tr>'
        for h in headers: html += f'<th class="text-nowrap">{h}</th>'
        html += '</tr></thead><tbody>'
        
        for row in data:
            html += '<tr>'
            html += f'<td>{row["序号"]}</td><td>{row["姓名"]}</td><td>{row["部门"]}</td>'
            for field in (field_names if field_names else []):
                val = row.get(field, '')
                display_val = (val[:20] + '...') if val and len(val) > 20 else val
                html += f'<td>{display_val}</td>'
            html += f'<td><button class="btn btn-sm btn-outline-primary py-0" onclick="openEditRecordModal({row["record_id"]})"><i class="fas fa-edit"></i> 修改</button></td></tr>'
            
        html += '</tbody></table></div>'
        return jsonify({'success': True, 'html': html})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/records/<int:record_id>/data', methods=['GET'])
def get_record_data(record_id):
    """人工补录 - 获取数据"""
    try:
        record = EmailRecord.query.get_or_404(record_id)
        task = SummaryTask.query.get(record.task_id)
        responses = TaskResponse.query.filter_by(record_id=record_id).all()
        current_data = {r.field_name: r.field_value for r in responses}
        return jsonify({'success': True, 'fields': task.get_template_fields(), 'data': current_data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/records/<int:record_id>/update', methods=['POST'])
def update_record_data(record_id):
    """人工补录 - 保存 (双写)"""
    print(f"🔍 收到修正: Record {record_id}")
    try:
        record = EmailRecord.query.get_or_404(record_id)
        task = SummaryTask.query.get(record.task_id)
        teacher = Teacher.query.get(record.teacher_id)
        form_data = request.form.to_dict()
        
        # 1. 更新EAV
        TaskResponse.query.filter_by(record_id=record_id).delete()
        clean_data = {}
        for k, v in form_data.items():
            if k != 'record_id':
                db.session.add(TaskResponse(record_id=record_id, field_name=k, field_value=v, field_type='string'))
                clean_data[k] = v
        
        # 2. 更新物理表
        if task.column_mapping:
            from utils.dynamic_db import dynamic_db
            col_mapping = task.get_column_mapping()
            teacher_info = {
                'teacher_id': teacher.teacher_id, 'teacher_name': teacher.teacher_name,
                'department': teacher.department, 'email': teacher.email,
                'reply_time': record.replied_time or datetime.now()
            }
            dynamic_db.save_response(task.task_id, teacher_info, clean_data, col_mapping)
        
        record.status = '已回复'
        if not record.replied_time: record.replied_time = datetime.now()
        
        db.session.commit()
        return jsonify({'success': True, 'message': '保存成功'})
    except Exception as e:
        db.session.rollback()
        print(f"❌ 保存失败: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/ai/query', methods=['POST'])
def ai_query():
    """AI 查询接口 (支持上下文)"""
    try:
        data = request.json
        task_id = data.get('task_id')
        # 前端传来的历史记录列表，最后一条是当前问题
        history = data.get('messages') 
        
        if not task_id or not history:
            return jsonify({'success': False, 'error': '参数错误'})
            
        success, result = ai_service.generate_and_execute_sql(task_id, history)
        
        if success:
            return jsonify({'success': True, 'result': result})
        else:
            return jsonify({'success': False, 'error': result})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
      
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5002)