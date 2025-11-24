from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

class Teacher(db.Model):
    """教师表"""
    __tablename__ = 'teachers'
    
    teacher_id = db.Column(db.Integer, primary_key=True)
    teacher_name = db.Column(db.String(50), nullable=False)
    department = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    id_card = db.Column(db.String(20))
    birthdate = db.Column(db.Date)
    title = db.Column(db.String(50))
    position = db.Column(db.String(50))
    education = db.Column(db.String(50))
    degree = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'teacher_id': self.teacher_id,
            'teacher_name': self.teacher_name,
            'department': self.department,
            'email': self.email,
            'phone': self.phone,
            'title': self.title,
            'position': self.position
        }

class SummaryTask(db.Model):
    """汇总任务表"""
    __tablename__ = 'summary_tasks'
    
    task_id = db.Column(db.Integer, primary_key=True)
    task_name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    deadline = db.Column(db.DateTime)
    template_path = db.Column(db.String(255))
    
    # 存储模板字段结构的JSON
    template_fields = db.Column(db.Text)
    
    def get_template_fields(self):
        """获取模板字段结构"""
        if self.template_fields:
            return json.loads(self.template_fields)
        return []
    
    def set_template_fields(self, fields):
        """设置模板字段结构"""
        self.template_fields = json.dumps(fields, ensure_ascii=False)

class EmailRecord(db.Model):
    """邮件记录表"""
    __tablename__ = 'email_records'
    
    record_id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('summary_tasks.task_id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.teacher_id'), nullable=False)
    sent_time = db.Column(db.DateTime, default=datetime.utcnow)
    replied_time = db.Column(db.DateTime)
    reply_title = db.Column(db.String(100))
    status = db.Column(db.String(20), default='未回复')
    
    # 冗余字段，优化查询性能
    teacher_name = db.Column(db.String(50))
    department = db.Column(db.String(50))
    
    # 关系
    task = db.relationship('SummaryTask', backref=db.backref('email_records', lazy=True))
    teacher = db.relationship('Teacher', backref=db.backref('email_records', lazy=True))

class TaskResponse(db.Model):
    """任务回复数据表"""
    __tablename__ = 'task_responses'
    
    response_id = db.Column(db.Integer, primary_key=True)
    record_id = db.Column(db.Integer, db.ForeignKey('email_records.record_id'), nullable=False)
    field_name = db.Column(db.String(100), nullable=False)
    field_value = db.Column(db.Text)
    field_type = db.Column(db.String(50))
    
    # 关系
    email_record = db.relationship('EmailRecord', backref=db.backref('responses', lazy=True))
    
    # 唯一约束
    __table_args__ = (
        db.UniqueConstraint('record_id', 'field_name', name='uq_record_field'),
    )