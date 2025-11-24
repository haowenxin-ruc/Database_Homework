from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
from models import db, Teacher, SummaryTask, EmailRecord, TaskResponse
from config import config
import os
from utils.email_utils import email_sender
from models import Teacher, EmailRecord
from utils.excel_utils import parse_excel_template
from utils.imap_utils import email_receiver
from utils.excel_utils import parse_reply_excel, parse_excel_template, merge_excel_files # 我们需要一个解析Excel数据的函数
import tempfile
from utils.imap_utils import email_receiver
from utils.excel_utils import parse_reply_excel
import base64
import os
from utils.data_summary import data_summary
from flask import send_file
from utils.advanced_analysis import advanced_analysis

def create_app():
    app = Flask(__name__)
    app.config.from_object(config)
    
    # 初始化数据库
    db.init_app(app)
    
    # 创建上传目录
    os.makedirs('uploads', exist_ok=True)
    os.makedirs('templates/excel', exist_ok=True)
  #  os.makedirs('exports', exist_ok=True)  # 新增导出目录

    return app

app = create_app()




import os
from datetime import datetime
from werkzeug.utils import secure_filename

# 允许上传的Excel文件扩展名
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 任务管理API
@app.route('/api/tasks', methods=['POST'])
def add_task():
    """创建汇总任务"""
    try:
        task_name = request.form.get('task_name')
        description = request.form.get('description')
        deadline_str = request.form.get('deadline')
        
        # 处理截止时间
        deadline = None
        if deadline_str:
            deadline = datetime.fromisoformat(deadline_str)
        
        # 创建任务
        task = SummaryTask(
            task_name=task_name,
            description=description,
            deadline=deadline
        )
        
        # 处理模板文件上传
        if 'template_file' in request.files:
            file = request.files['template_file']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # 保存模板文件
                template_dir = 'templates/excel'
                os.makedirs(template_dir, exist_ok=True)
                template_path = os.path.join(template_dir, f"task_{task_name}_{filename}")
                file.save(template_path)
                task.template_path = template_path
                
                # 解析Excel模板字段
                fields = parse_excel_template(template_path)
                task.set_template_fields(fields)
                
        db.session.add(task)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '任务创建成功'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})
# @app.route('/api/tasks/<int:task_id>/data-preview')
# def get_task_data_preview(task_id):
#     """获取任务数据预览"""
#     try:
#         task = SummaryTask.query.get(task_id)
#         if not task:
#             return jsonify({'success': False, 'error': '任务不存在'})
        
#         # 获取已回复的记录
#         replied_records = EmailRecord.query.filter_by(
#             task_id=task_id, 
#             status='已回复'
#         ).limit(10).all()  # 只预览前10条
        
#         if not replied_records:
#             return jsonify({
#                 'success': True, 
#                 'html': '<div class="text-center py-4"><p class="text-muted">暂无回复数据</p></div>'
#             })
        
#         # 构建预览数据
#         preview_data = []
#         template_fields = task.get_template_fields() if task.template_fields else []
        
#         for i, record in enumerate(replied_records, 1):
#             teacher = Teacher.query.get(record.teacher_id)
#             if not teacher:
#                 continue
            
#             row_data = {"序号": i, "姓名": teacher.teacher_name, "所在系": teacher.department}
            
#             # 获取回复数据
#             responses = TaskResponse.query.filter_by(record_id=record.record_id).all()
#             response_dict = {resp.field_name: resp.field_value for resp in responses}
            
#             # 添加模板字段
#             if template_fields:
#                 for field in template_fields[:3]:  # 只显示前3个字段
#                     field_name = field['name']
#                     row_data[field_name] = response_dict.get(field_name, '')
#             else:
#                 # 显示前3个回复字段
#                 for j, (field_name, value) in enumerate(response_dict.items()):
#                     if j >= 3:
#                         break
#                     row_data[field_name] = value
            
#             preview_data.append(row_data)
        
#         # 生成HTML表格
#         if not preview_data:
#             html = '<div class="text-center py-4"><p class="text-muted">暂无回复数据</p></div>'
#         else:
#             # 获取表头
#             headers = list(preview_data[0].keys())
            
#             html = '<div class="table-responsive"><table class="table table-sm table-striped"><thead><tr>'
#             for header in headers:
#                 html += f'<th>{header}</th>'
#             html += '</tr></thead><tbody>'
            
#             for row in preview_data:
#                 html += '<tr>'
#                 for header in headers:
#                     value = row.get(header, '')
#                     html += f'<td>{value}</td>'
#                 html += '</tr>'
            
#             html += '</tbody></table>'
#             html += '<div class="text-muted text-center mt-2">显示前10条记录预览</div></div>'
        
#         return jsonify({'success': True, 'html': html})
        
#     except Exception as e:
#         return jsonify({'success': False, 'error': str(e)})
# @app.route('/tasks/<int:task_id>/summary')
# def task_summary(task_id):
#     """任务数据汇总页面"""
#     try:
#         task = SummaryTask.query.get_or_404(task_id)
#         stats = data_summary.get_summary_statistics(task_id)
        
#         if not stats:
#             stats = {
#                 'total_teachers': 0,
#                 'replied_teachers': 0,
#                 'not_replied_teachers': 0,
#                 'reply_rate': 0,
#                 'field_stats': {}
#             }
        
#         return render_template('task_summary.html', task=task, stats=stats)
        
#     except Exception as e:
#         flash(f'加载汇总页面失败: {str(e)}')
#         return redirect(url_for('manage_tasks'))
        
@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    """删除任务 - 修复外键约束问题"""
    try:
        task = SummaryTask.query.get_or_404(task_id)
        
        print(f"开始删除任务: {task.task_name} (ID: {task_id})")
        
        # 1. 先删除所有相关的 TaskResponse 记录
        email_records = EmailRecord.query.filter_by(task_id=task_id).all()
        email_record_ids = [record.record_id for record in email_records]
        
        print(f"找到 {len(email_record_ids)} 个相关的邮件记录")
        
        if email_record_ids:
            # 删除所有相关的 TaskResponse
            task_responses = TaskResponse.query.filter(
                TaskResponse.record_id.in_(email_record_ids)
            ).all()
            
            print(f"删除 {len(task_responses)} 个任务回复记录")
            for response in task_responses:
                db.session.delete(response)
        
        # 2. 删除所有相关的 EmailRecord 记录
        email_records_count = EmailRecord.query.filter_by(task_id=task_id).delete()
        print(f"删除 {email_records_count} 个邮件记录")
        
        # 3. 最后删除任务本身
        db.session.delete(task)
        db.session.commit()
        
        print("✅ 任务删除成功")
        return jsonify({'success': True, 'message': '任务删除成功'})
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ 删除任务失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

# @app.route('/api/tasks/<int:task_id>/generate-summary')
# def generate_task_summary(task_id):
#     """生成任务汇总表"""
#     try:
#         success, result = data_summary.generate_task_summary(task_id)
        
#         if success:
#             # 返回文件下载路径
#             filename = os.path.basename(result)
#             return jsonify({
#                 'success': True,
#                 'message': '汇总表生成成功',
#                 'download_url': f'/api/download-summary/{filename}',
#                 'file_path': result
#             })
#         else:
#             return jsonify({'success': False, 'error': result})
            
#     except Exception as e:
#         return jsonify({'success': False, 'error': str(e)})

# @app.route('/api/tasks/<int:task_id>/summary-stats')
# def get_task_summary_stats(task_id):
#     """获取任务汇总统计"""
#     try:
#         stats = data_summary.get_summary_statistics(task_id)
        
#         if stats:
#             return jsonify({'success': True, 'stats': stats})
#         else:
#             return jsonify({'success': False, 'error': '获取统计信息失败'})
            
#     except Exception as e:
#         return jsonify({'success': False, 'error': str(e)})

# @app.route('/api/download-summary/<filename>')
# def download_summary(filename):
#     """下载汇总表文件"""
#     try:
#         file_path = os.path.join('exports', filename)
        
#         if os.path.exists(file_path):
#             return send_file(file_path, as_attachment=True, download_name=filename)
#         else:
#             return jsonify({'success': False, 'error': '文件不存在'})
            
#     except Exception as e:
#         return jsonify({'success': False, 'error': str(e)})
    
@app.route('/api/tasks/<int:task_id>/send-emails', methods=['POST'])
def send_task_emails(task_id):
    """发送任务邮件给所有教师"""
    try:
        task = SummaryTask.query.get_or_404(task_id)
        teachers = Teacher.query.all()
        
        sent_count = 0
        failed_emails = []
        
        for teacher in teachers:
            # 创建邮件记录
            email_record = EmailRecord(
                task_id=task_id,
                teacher_id=teacher.teacher_id,
                teacher_name=teacher.teacher_name,
                department=teacher.department,
                status='未回复'
            )
            db.session.add(email_record)
            db.session.flush()  # 获取record_id
            
            # 发送邮件
            subject = f"请填写汇总表：{task.task_name}"
            content = f"""
尊敬的{teacher.teacher_name}老师：

请您填写附件中的汇总表，并在截止时间前回复本邮件。

任务名称：{task.task_name}
任务描述：{task.description or "无描述"}
截止时间：{task.deadline.strftime('%Y-%m-%d %H:%M') if task.deadline else "未设置"}

请注意：
1. 请直接回复本邮件，不要修改邮件主题
2. 附件中已包含需要填写的表格
3. 如有问题，请联系科研秘书

谢谢！
"""
            # 发送邮件（如果配置了邮件服务器）
            if config.MAIL_SERVER and config.MAIL_USERNAME and config.MAIL_PASSWORD:
                success = email_sender.send_email(
                    to_email=teacher.email,
                    subject=subject,
                    content=content,
                    attachment_path=task.template_path
                )
            else:
                # 如果没有配置邮件服务器，模拟发送成功
                success = True
                print(f"模拟发送邮件给 {teacher.email}")
            
            if success:
                email_record.sent_time = datetime.utcnow()
                sent_count += 1
            else:
                failed_emails.append(teacher.email)
                db.session.delete(email_record)  # 发送失败，删除记录
        
        db.session.commit()
        
        if failed_emails:
            return jsonify({
                'success': True, 
                'message': f'邮件发送完成！成功发送 {sent_count} 封，失败 {len(failed_emails)} 封',
                'failed_emails': failed_emails
            })
        else:
            return jsonify({
                'success': True, 
                'message': f'成功发送 {sent_count} 封邮件'
            })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

# 基础路由
@app.route('/')
def index():
    """首页"""
    teacher_count = Teacher.query.count()
    task_count = SummaryTask.query.count()
    pending_count = EmailRecord.query.filter_by(status='未回复').count()
    completed_count = EmailRecord.query.filter_by(status='已回复').count()
    
    return render_template('index.html',
                         teacher_count=teacher_count,
                         task_count=task_count,
                         pending_count=pending_count,
                         completed_count=completed_count)
    

@app.route('/teachers')
def manage_teachers():
    """教师管理页面"""
    teachers = Teacher.query.all()
    return render_template('teachers.html', teachers=teachers)

@app.route('/api/teachers', methods=['POST'])
def add_teacher():
    """添加教师"""
    try:
        data = request.form
        
        teacher = Teacher(
            teacher_name=data.get('teacher_name'),
            department=data.get('department'),
            email=data.get('email'),
            phone=data.get('phone'),
            title=data.get('title'),
            position=data.get('position')
        )
        
        db.session.add(teacher)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '教师添加成功'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})
@app.route('/api/tasks/<int:task_id>/fields')
def get_task_fields(task_id):
    """获取任务的模板字段"""
    try:
        task = SummaryTask.query.get_or_404(task_id)
        fields = task.get_template_fields()
        
        return jsonify({
            'success': True,
            'task_name': task.task_name,
            'fields': fields
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    
@app.route('/api/teachers/<int:teacher_id>', methods=['DELETE'])
def delete_teacher(teacher_id):
    """删除教师（修复外键约束问题）"""
    try:
        teacher = Teacher.query.get_or_404(teacher_id)
        
        # 先删除相关的邮件记录
        email_records = EmailRecord.query.filter_by(teacher_id=teacher_id).all()
        for record in email_records:
            # 删除相关的附件记录（如果有）
            # attachments = Attachment.query.filter_by(record_id=record.record_id).all()
            # for attachment in attachments:
            #     db.session.delete(attachment)
            
            # 删除相关的回复数据（如果有）
            responses = TaskResponse.query.filter_by(record_id=record.record_id).all()
            for response in responses:
                db.session.delete(response)
            
            # 删除邮件记录
            db.session.delete(record)
        
        # 再删除教师
        db.session.delete(teacher)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '教师删除成功'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}) 
# [file name]: app.py (修改 check_task_replies 函数)
# [file content begin]
@app.route('/api/tasks/<int:task_id>/check-replies')
def check_task_replies(task_id):
    """检查任务的回复邮件"""
    try:
        task = SummaryTask.query.get_or_404(task_id)
        print(f"检查任务回复: {task.task_name}")
        
        # 搜索相关回复邮件
        emails = email_receiver.search_reply_emails(task.task_name)
        print(f"找到 {len(emails)} 封相关邮件")
        
        new_replies = []
        processed_count = 0
        
        for i, email_data in enumerate(emails):
            print(f"\n=== 处理第 {i+1} 封邮件 ===")
            print(f"发件人: {email_data['from_email']}")
            print(f"主题: {email_data['subject']}")
            print(f"附件数量: {len(email_data['attachments'])}")
            
            # 根据邮箱查找教师
            teacher = Teacher.query.filter_by(email=email_data['from_email']).first()
            if not teacher:
                print(f"❌ 未找到对应教师: {email_data['from_email']}")
                # 打印所有教师邮箱帮助调试
                all_teachers = Teacher.query.all()
                print("系统中所有教师邮箱:")
                for t in all_teachers:
                    print(f"  - {t.teacher_name}: {t.email}")
                continue
            
            print(f"✅ 找到对应教师: {teacher.teacher_name}")
            
            # 查找邮件记录
            email_record = EmailRecord.query.filter_by(
                task_id=task_id, 
                teacher_id=teacher.teacher_id
            ).first()
            
            if not email_record:
                print(f"❌ 未找到邮件记录: {teacher.teacher_name}")
                print(f"任务ID: {task_id}, 教师ID: {teacher.teacher_id}")
                # 打印该教师的所有邮件记录
                teacher_records = EmailRecord.query.filter_by(teacher_id=teacher.teacher_id).all()
                print(f"该教师的所有邮件记录: {len(teacher_records)} 条")
                for rec in teacher_records:
                    print(f"  - 任务ID: {rec.task_id}, 状态: {rec.status}")
                continue
            
            print(f"当前状态: {email_record.status}")
            
            if email_record.status == '已回复':
                print(f"⏭️ 该教师已回复: {teacher.teacher_name}")
                continue
            
            # 处理附件
            if email_data['attachments']:
                for j, attachment in enumerate(email_data['attachments']):
                    print(f"检查附件 {j+1}: {attachment['filename']}")
                    
                    # 解码后的文件名检查
                    filename = attachment['filename'].lower()
                    print(f"解码后文件名(小写): {filename}")
                    
                    if filename.endswith(('.xlsx', '.xls')):
                        print(f"✅ 处理Excel附件: {attachment['filename']}")
                        
                        # 解析Excel数据
                        task_fields = task.get_template_fields()
                        reply_data = parse_reply_excel(attachment['data'], task_fields)
                        
                        if reply_data:
                            print(f"解析到数据: {reply_data}")
                            
                            # 保存回复数据到TaskResponse表
                            for field_name, field_value in reply_data.items():
                                task_response = TaskResponse(
                                    record_id=email_record.record_id,
                                    field_name=field_name,
                                    field_value=field_value,
                                    field_type='string'
                                )
                                db.session.add(task_response)
                            
                            # 更新邮件记录状态
                            email_record.status = '已回复'
                            email_record.replied_time = email_data['date']
                            email_record.reply_title = email_data['subject']
                            
                            db.session.commit()
                            
                            new_replies.append({
                                'teacher_name': teacher.teacher_name,
                                'email': teacher.email,
                                'reply_time': email_data['date'].strftime('%Y-%m-%d %H:%M')
                            })
                            processed_count += 1
                            print(f"✅ 成功处理 {teacher.teacher_name} 的回复")
                        else:
                            print(f"❌ 解析附件失败，无有效数据")
                        break
                else:
                    print(f"📎 有附件但没有Excel文件，附件列表:")
                    for att in email_data['attachments']:
                        print(f"  - {att['filename']}")
        
        print(f"\n=== 处理完成 ===")
        print(f"处理了 {processed_count} 个新回复")
        print(f"新回复列表: {new_replies}")
        
        return jsonify({
            'success': True,
            'message': f'检查完成！处理了 {processed_count} 个新回复',
            'new_replies': new_replies,
            'total_emails': len(emails)
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ 检查回复时出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})
# [file content end]
@app.route('/api/tasks/<int:task_id>/reply-status')
def get_reply_status(task_id):
    """获取任务回复状态"""
    try:
        task = SummaryTask.query.get_or_404(task_id)
        
        # 统计回复情况
        total_teachers = EmailRecord.query.filter_by(task_id=task_id).count()
        replied_count = EmailRecord.query.filter_by(task_id=task_id, status='已回复').count()
        not_replied_count = total_teachers - replied_count
        
        # 获取已回复教师列表
        replied_records = EmailRecord.query.filter_by(task_id=task_id, status='已回复').all()
        replied_teachers = []
        
        for record in replied_records:
            teacher = Teacher.query.get(record.teacher_id)
            if teacher:
                replied_teachers.append({
                    'teacher_name': teacher.teacher_name,
                    'department': teacher.department,
                    'email': teacher.email,
                    'reply_time': record.replied_time.strftime('%Y-%m-%d %H:%M') if record.replied_time else '未知'
                })
        
        # 获取未回复教师列表
        not_replied_records = EmailRecord.query.filter_by(task_id=task_id, status='未回复').all()
        not_replied_teachers = []
        
        for record in not_replied_records:
            teacher = Teacher.query.get(record.teacher_id)
            if teacher:
                not_replied_teachers.append({
                    'teacher_name': teacher.teacher_name,
                    'department': teacher.department,
                    'email': teacher.email
                })
        
        return jsonify({
            'success': True,
            'task_name': task.task_name,
            'statistics': {
                'total': total_teachers,
                'replied': replied_count,
                'not_replied': not_replied_count,
                'reply_rate': round((replied_count / total_teachers * 100), 2) if total_teachers > 0 else 0
            },
            'replied_teachers': replied_teachers,
            'not_replied_teachers': not_replied_teachers
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})







    
@app.route('/tasks/<int:task_id>/replies')
def task_replies(task_id):
    """任务回复状态页面"""
    try:
        task = SummaryTask.query.get_or_404(task_id)
        
        # 获取回复状态数据
        status_response = get_reply_status(task_id)
        if status_response.is_json:
            status_data = status_response.get_json()
            if status_data['success']:
                return render_template('task_replies.html', 
                                    task=task,
                                    statistics=status_data['statistics'],
                                    replied_teachers=status_data['replied_teachers'],
                                    not_replied_teachers=status_data['not_replied_teachers'])
        
        # 如果获取失败，显示空数据
        return render_template('task_replies.html', 
                            task=task,
                            statistics={'total': 0, 'replied': 0, 'not_replied': 0, 'reply_rate': 0},
                            replied_teachers=[],
                            not_replied_teachers=[])
        
    except Exception as e:
        return render_template('task_replies.html', 
                            task=task,
                            statistics={'total': 0, 'replied': 0, 'not_replied': 0, 'reply_rate': 0},
                            replied_teachers=[],
                            not_replied_teachers=[])
                
@app.route('/tasks')
def manage_tasks():
    """任务管理页面"""
    tasks = SummaryTask.query.all()
    return render_template('tasks.html', tasks=tasks)






@app.route('/api/tasks/<int:task_id>/generate-summary')
def generate_task_summary(task_id):
    """生成任务汇总表"""
    try:
        success, result = data_summary.generate_task_summary(task_id)
        
        if success:
            # 返回文件下载路径
            filename = os.path.basename(result)
            return jsonify({
                'success': True,
                'message': '汇总表生成成功',
                'download_url': f'/api/download-summary/{filename}',
                'file_path': result
            })
        else:
            return jsonify({'success': False, 'error': result})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/tasks/<int:task_id>/summary-stats')
def get_task_summary_stats(task_id):
    """获取任务汇总统计"""
    try:
        stats = data_summary.get_summary_statistics(task_id)
        
        if stats:
            return jsonify({'success': True, 'stats': stats})
        else:
            return jsonify({'success': False, 'error': '获取统计信息失败'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/download-summary/<filename>')
def download_summary(filename):
    """下载汇总表文件"""
    try:
        file_path = os.path.join('exports', filename)
        
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True, download_name=filename)
        else:
            return jsonify({'success': False, 'error': '文件不存在'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/tasks/<int:task_id>/data-preview')
def get_task_data_preview(task_id):
    """获取任务数据预览"""
    try:
        task = SummaryTask.query.get(task_id)
        if not task:
            return jsonify({'success': False, 'error': '任务不存在'})
        
        # 获取已回复的记录
        replied_records = EmailRecord.query.filter_by(
            task_id=task_id, 
            status='已回复'
        ).limit(10).all()  # 只预览前10条
        
        if not replied_records:
            return jsonify({
                'success': True, 
                'html': '<div class="text-center py-4"><p class="text-muted">暂无回复数据</p></div>'
            })
        
        # 构建预览数据
        preview_data = []
        template_fields = task.get_template_fields() if task.template_fields else []
        
        for i, record in enumerate(replied_records, 1):
            teacher = Teacher.query.get(record.teacher_id)
            if not teacher:
                continue
            
            row_data = {"序号": i, "姓名": teacher.teacher_name, "所在系": teacher.department}
            
            # 获取回复数据
            responses = TaskResponse.query.filter_by(record_id=record.record_id).all()
            response_dict = {resp.field_name: resp.field_value for resp in responses}
            
            # 添加模板字段
            if template_fields:
                for field in template_fields[:3]:  # 只显示前3个字段
                    field_name = field['name']
                    row_data[field_name] = response_dict.get(field_name, '')
            else:
                # 显示前3个回复字段
                for j, (field_name, value) in enumerate(response_dict.items()):
                    if j >= 3:
                        break
                    row_data[field_name] = value
            
            preview_data.append(row_data)
        
        # 生成HTML表格
        if not preview_data:
            html = '<div class="text-center py-4"><p class="text-muted">暂无回复数据</p></div>'
        else:
            # 获取表头
            headers = list(preview_data[0].keys())
            
            html = '<div class="table-responsive"><table class="table table-sm table-striped"><thead><tr>'
            for header in headers:
                html += f'<th>{header}</th>'
            html += '</tr></thead><tbody>'
            
            for row in preview_data:
                html += '<tr>'
                for header in headers:
                    value = row.get(header, '')
                    html += f'<td>{value}</td>'
                html += '</tr>'
            
            html += '</tbody></table>'
            html += '<div class="text-muted text-center mt-2">显示前10条记录预览</div></div>'
        
        return jsonify({'success': True, 'html': html})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/tasks/<int:task_id>/summary')
def task_summary(task_id):
    """任务数据汇总页面"""
    try:
        task = SummaryTask.query.get_or_404(task_id)
        stats = data_summary.get_summary_statistics(task_id)
        
        if not stats:
            stats = {
                'total_teachers': 0,
                'replied_teachers': 0,
                'not_replied_teachers': 0,
                'reply_rate': 0,
                'field_stats': {}
            }
        
        return render_template('task_summary.html', task=task, stats=stats)
        
    except Exception as e:
        flash(f'加载汇总页面失败: {str(e)}')
        return redirect(url_for('manage_tasks'))

@app.route('/api/tasks/<int:task_id>/analysis/comprehensive')
def get_comprehensive_analysis(task_id):
    """获取综合分析报告"""
    try:
        analysis_data = advanced_analysis.get_comprehensive_analysis(task_id)
        
        if analysis_data:
            return jsonify({'success': True, 'analysis': analysis_data})
        else:
            return jsonify({'success': False, 'error': '分析数据获取失败'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/tasks/<int:task_id>/analysis/trend')
def get_trend_analysis(task_id):
    """获取趋势分析"""
    try:
        trend_data = advanced_analysis.get_reply_trend_analysis(task_id)
        
        if trend_data:
            return jsonify({'success': True, 'trend': trend_data})
        else:
            return jsonify({'success': False, 'error': '趋势分析数据获取失败'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/tasks/<int:task_id>/analysis/department')
def get_department_analysis(task_id):
    """获取部门分析"""
    try:
        department_data = advanced_analysis.get_department_analysis(task_id)
        
        if department_data:
            return jsonify({'success': True, 'departments': department_data})
        else:
            return jsonify({'success': False, 'error': '部门分析数据获取失败'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/tasks/<int:task_id>/analysis/response-time')
def get_response_time_analysis(task_id):
    """获取回复时间分析"""
    try:
        time_data = advanced_analysis.get_response_time_analysis(task_id)
        
        if time_data:
            return jsonify({'success': True, 'time_analysis': time_data})
        else:
            return jsonify({'success': False, 'error': '回复时间分析数据获取失败'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

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
    """AI助手页面"""
    return render_template('ai_assistant.html')

if __name__ == '__main__':
    with app.app_context():
        # 创建数据库表
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)