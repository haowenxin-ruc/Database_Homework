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
from utils.advanced_analysis import advanced_analysis  # 确保这里正确引用
from utils.dynamic_db import dynamic_db
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
    """教师管理页面"""
    teachers = Teacher.query.order_by(Teacher.created_at.desc()).all()
    return render_template('teachers.html', teachers=teachers)

@app.route('/tasks')
def manage_tasks():
    """任务管理页面"""
    tasks = SummaryTask.query.order_by(SummaryTask.create_time.desc()).all()
    # 【新增】获取所有教师，传给前端
    teachers = Teacher.query.order_by(Teacher.teacher_name).all()
    
    return render_template('tasks.html', tasks=tasks, teachers=teachers, now=datetime.now())

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
    """高级分析页面（图表展示页）"""
    try:
        task = SummaryTask.query.get_or_404(task_id)
        return render_template('advanced_analysis.html', task=task)
    except Exception as e:
        flash(f'加载高级分析页面失败: {str(e)}')
        return redirect(url_for('task_summary', task_id=task_id))

@app.route('/ai-assistant')
def ai_assistant():
    return render_template('ai_assistant.html')


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

# [file name]: app.py (添加到教师管理 API 区域)

# [file name]: app.py

# ... 其他代码 ...

# 1. 确保有这个获取详情的接口 (用于回显数据)
@app.route('/api/teachers/<int:teacher_id>', methods=['GET'])
def get_teacher_details(teacher_id):
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

# 2. 【重点检查】确保有这个更新接口，并且 methods=['PUT']
@app.route('/api/teachers/<int:teacher_id>', methods=['PUT'])
def update_teacher(teacher_id):
    try:
        teacher = Teacher.query.get_or_404(teacher_id)
        data = request.form # 获取前端表单数据
        
        # 打印日志方便调试
        print(f"正在更新教师 {teacher_id}: {data}")
        
        new_email = data.get('email')
        
        # 查重逻辑：如果改了邮箱，且邮箱被别人占用了
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
        return jsonify({'success': True, 'message': '更新成功'})
        
    except Exception as e:
        db.session.rollback()
        print(f"更新失败: {e}") # 打印错误到后台
        return jsonify({'success': False, 'error': str(e)})

# ... 其他代码 ...
    """更新教师信息"""
    try:
        teacher = Teacher.query.get_or_404(teacher_id)
        data = request.form
        
        new_email = data.get('email')
        
        # 检查邮箱是否被其他教师占用 (排除自己)
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
    """创建汇总任务 + 动态建表"""
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
        db.session.flush() # 此时 task.task_id 已生成
        
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
                
                # 【新增】动态创建数据库物理表
                success, result = dynamic_db.create_task_table(task.task_id, fields)
                if success:
                    # 保存列名映射关系，供后续写入数据使用
                    task.set_column_mapping(result)
                        # 2. 【新增】处理选中的教师
        # request.form.getlist 可以获取多选框的所有值
        selected_teacher_ids = request.form.getlist('teacher_ids')
        
        if not selected_teacher_ids:
            # 为了防止创建空任务，如果没有选人，默认不创建记录，或者强制要求选人
            pass 
        else:
            for tid in selected_teacher_ids:
                teacher = Teacher.query.get(tid)
                if teacher:
                    # 预先创建记录，状态为 "未发送"
                    record = EmailRecord(
                        task_id=task.task_id,
                        teacher_id=teacher.teacher_id,
                        teacher_name=teacher.teacher_name,
                        department=teacher.department,
                        status='未发送' # 新增一种状态
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
        
        # ... 原有的删除逻辑 ...
        records = EmailRecord.query.filter_by(task_id=task_id).all()
        ids = [r.record_id for r in records]
        if ids:
            TaskResponse.query.filter(TaskResponse.record_id.in_(ids)).delete(synchronize_session=False)
        EmailRecord.query.filter_by(task_id=task_id).delete()
        
        # 【新增】删除动态物理表
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
    """
    发送任务通知邮件
    逻辑：只发送给状态为 '未发送' 的记录 (即创建任务时选中的教师)
    """
    try:
        task = SummaryTask.query.get_or_404(task_id)
        
        # 1. 查找该任务下，所有等待发送的记录
        # 注意：这里只查 '未发送' 的。如果状态是 '未回复' (说明已发过) 或 '已回复'，则不重发。
        pending_records = EmailRecord.query.filter_by(task_id=task_id, status='未发送').all()
        
        # 2. 检查是否没有待发送记录
        if not pending_records:
            # 进一步检查：是不是因为这个任务根本没选人（或者是一个旧任务）
            total_records = EmailRecord.query.filter_by(task_id=task_id).count()
            if total_records == 0:
                return jsonify({
                    'success': False, 
                    'message': '该任务未关联任何教师，无法发送。请删除任务重新创建并选择教师。'
                })
            else:
                return jsonify({
                    'success': True, 
                    'message': '没有待发送的邮件 (所有选定教师均已发送通知)'
                })

        sent_count = 0
        failed_list = []
        
        # 3. 遍历待发送列表
        for record in pending_records:
            teacher = Teacher.query.get(record.teacher_id)
            if not teacher: 
                continue
            
            # 构建邮件内容
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
            # 发送邮件
            try:
                if config.MAIL_SERVER:
                    success = email_sender.send_email(
                        to_email=teacher.email,
                        subject=subject,
                        content=content,
                        attachment_path=task.template_path
                    )
                else:
                    # 开发模式模拟发送
                    print(f"[Dev] 模拟发送邮件给: {teacher.email}")
                    success = True

                if success:
                    # 【关键】发送成功，状态流转：未发送 -> 未回复
                    record.status = '未回复'
                    record.sent_time = datetime.now()
                    sent_count += 1
                else:
                    # 发送失败，记录名字，状态保持 '未发送' 以便重试
                    failed_list.append(teacher.teacher_name)
                    
            except Exception as e:
                print(f"发送给 {teacher.teacher_name} 异常: {e}")
                failed_list.append(teacher.teacher_name)
        
        # 4. 提交数据库更改
        db.session.commit()
        
        # 5. 返回结果
        msg = f"本次成功发送 {sent_count} 封邮件。"
        if failed_list:
            msg += f" 失败 {len(failed_list)} 人: {', '.join(failed_list[:5])}..."
            if len(failed_list) > 5: msg += " 等"
            return jsonify({'success': True, 'message': msg, 'warning': True})
            
        return jsonify({'success': True, 'message': msg})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f"系统错误: {str(e)}"})
    
@app.route('/api/tasks/<int:task_id>/check-replies')
def check_task_replies(task_id):
    """检查回复 + 同步写入动态表"""
    try:
        task = SummaryTask.query.get_or_404(task_id)
        emails = email_receiver.search_reply_emails(task.task_name)
        processed_count = 0
        new_replies = []
        
        # 获取列映射关系
        col_mapping = task.get_column_mapping()
        
        for email_data in emails:
            teacher = Teacher.query.filter_by(email=email_data['from_email']).first()
            if not teacher: continue
            
            record = EmailRecord.query.filter_by(task_id=task_id, teacher_id=teacher.teacher_id).first()
            
            # 如果没有记录，自动创建（应对自发回复的情况）
            if not record:
                 record = EmailRecord(task_id=task_id, teacher_id=teacher.teacher_id, 
                                      teacher_name=teacher.teacher_name, department=teacher.department)
                 db.session.add(record)
                 db.session.flush()

            # 如果已经回复过，跳过 (或者你可以选择允许更新，这里暂定跳过)
            if record.status == '已回复': continue
            
            if email_data['attachments']:
                for att in email_data['attachments']:
                    if att['filename'].lower().endswith(('.xlsx', '.xls')):
                        fields = task.get_template_fields()
                        reply_data = parse_reply_excel(att['data'], fields)
                        
                        if reply_data:
                            # 1. 写入原有 EAV 表 (TaskResponse) - 保持前端兼容
                            for k, v in reply_data.items():
                                db.session.add(TaskResponse(record_id=record.record_id, field_name=k, field_value=v))
                            
                            # 2. 【新增】写入动态物理表 (task_data_xxx) - 供 AI 使用
                            teacher_info = {
                                'teacher_id': teacher.teacher_id,
                                'teacher_name': teacher.teacher_name,
                                'department': teacher.department,
                                'email': teacher.email,
                                'reply_time': email_data['date']
                            }
                            dynamic_db.save_response(task.task_id, teacher_info, reply_data, col_mapping)
                            
                            # 更新状态
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
        
        # 1. 获取逻辑映射关系 (Excel -> DB)
        mapping = task.get_column_mapping()
        
        # 2. 获取物理表结构 (直接查询 SQLite 系统表)
        try:
            # PRAGMA table_info 是 SQLite 查看表结构的命令
            result = db.session.execute(text(f"PRAGMA table_info({table_name})"))
            columns_info = [{'cid': row[0], 'name': row[1], 'type': row[2]} for row in result]
            table_exists = len(columns_info) > 0
        except Exception as e:
            table_exists = False
            columns_info = []

        # 3. 如果表存在，查询前 1 条数据看看
        sample_data = {}
        if table_exists:
            try:
                # 获取第一行数据
                row = db.session.execute(text(f"SELECT * FROM {table_name} LIMIT 1")).first()
                if row:
                    # 将 row 转换为字典 (row.keys() 在某些版本可能不可用，需配合 columns_info)
                    # SQLAlchemy row 可以直接转 dict 或者通过下标访问
                    # 这里简单处理，假设 columns_info 顺序和 row 一致
                    for idx, col in enumerate(columns_info):
                        sample_data[col['name']] = row[idx]
            except Exception as e:
                print(f"获取样本数据失败: {e}")

        return jsonify({
            'success': True,
            'task_name': task.task_name,
            'table_name': table_name,
            'table_exists': table_exists,
            'column_mapping': mapping, # 逻辑映射
            'physical_columns': columns_info, # 物理列
            'sample_data': sample_data # 样本数据
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
# [file name]: app.py


# ==========================================
# 4. API 路由 - 数据分析与图表 (Analysis API)
# 【重要】这里完全保留了你之前的所有图表数据接口
# ==========================================

@app.route('/api/tasks/<int:task_id>/analysis/comprehensive')
def get_comprehensive_analysis(task_id):
    """获取综合分析报告（包含所有图表数据）"""
    try:
        data = advanced_analysis.get_comprehensive_analysis(task_id)
        if data:
            return jsonify({'success': True, 'analysis': data})
        return jsonify({'success': False, 'error': '分析数据获取失败'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/tasks/<int:task_id>/analysis/trend')
def get_trend_analysis(task_id):
    """获取趋势分析（折线图数据）"""
    try:
        trend_data = advanced_analysis.get_reply_trend_analysis(task_id)
        if trend_data:
            return jsonify({'success': True, 'trend': trend_data})
        return jsonify({'success': False, 'error': '趋势数据获取失败'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/tasks/<int:task_id>/analysis/department')
def get_department_analysis(task_id):
    """获取部门分析（饼图/柱状图数据）"""
    try:
        department_data = advanced_analysis.get_department_analysis(task_id)
        if department_data:
            return jsonify({'success': True, 'departments': department_data})
        return jsonify({'success': False, 'error': '部门数据获取失败'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/tasks/<int:task_id>/analysis/response-time')
def get_response_time_analysis(task_id):
    """获取回复时间分析（直方图数据）"""
    try:
        time_data = advanced_analysis.get_response_time_analysis(task_id)
        if time_data:
            return jsonify({'success': True, 'time_analysis': time_data})
        return jsonify({'success': False, 'error': '时间分析数据获取失败'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ==========================================
# 5. API 路由 - 导出与下载
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
    """汇总数据预览表格"""
    try:
        task = SummaryTask.query.get(task_id)
        records = EmailRecord.query.filter_by(task_id=task_id, status='已回复').limit(10).all()
        if not records:
            return jsonify({'success': True, 'html': '<div class="text-center p-4 text-muted">暂无回复数据</div>'})
        
        data = []
        fields = task.get_template_fields()
        field_names = [f['name'] for f in fields] if fields else []
        
        for idx, rec in enumerate(records, 1):
            t = Teacher.query.get(rec.teacher_id)
            row = {'序号': idx, '姓名': t.teacher_name, '部门': t.department}
            responses = TaskResponse.query.filter_by(record_id=rec.record_id).all()
            resp_dict = {r.field_name: r.field_value for r in responses}
            
            display_cols = field_names[:5] if field_names else list(resp_dict.keys())[:5]
            for col in display_cols:
                row[col] = resp_dict.get(col, '')
            data.append(row)
            
        headers = list(data[0].keys())
        html = '<table class="table table-sm table-striped"><thead><tr>' + \
               ''.join([f'<th>{h}</th>' for h in headers]) + '</tr></thead><tbody>' + \
               ''.join(['<tr>' + ''.join([f'<td>{row[k]}</td>' for k in headers]) + '</tr>' for row in data]) + \
               '</tbody></table>'
        return jsonify({'success': True, 'html': html})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)