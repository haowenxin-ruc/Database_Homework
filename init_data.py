from app import app, db
from models import Teacher, SummaryTask
from datetime import datetime, timedelta

def init_sample_data():
    with app.app_context():
        # 清空现有数据
        db.drop_all()
        db.create_all()
        
        # 添加示例教师
        teachers = [
            Teacher(
                teacher_name="张教授",
                department="计算机科学",
                email="zhang@university.edu.cn",
                phone="13800138000",
                title="教授",
                position="系主任"
            ),
            Teacher(
                teacher_name="李教授", 
                department="计算机科学",
                email="li@university.edu.cn",
                phone="13800138001",
                title="教授"
            ),
            Teacher(
                teacher_name="王老师",
                department="软件工程", 
                email="wang@university.edu.cn",
                phone="13800138002",
                title="讲师"
            ),
            Teacher(
                teacher_name="赵副教授",
                department="人工智能",
                email="zhao@university.edu.cn", 
                phone="13800138003",
                title="副教授"
            )
        ]
        
        for teacher in teachers:
            db.session.add(teacher)
        
        # 添加示例任务
        tasks = [
            SummaryTask(
                task_name="人工智能应用案例单位推荐汇总表",
                description="收集各学院人工智能应用案例推荐信息",
                deadline=datetime.now() + timedelta(days=7)
            ),
            SummaryTask(
                task_name="基金申报汇总",
                description="年度科研基金项目申报信息汇总", 
                deadline=datetime.now() + timedelta(days=14)
            )
        ]
        
        for task in tasks:
            db.session.add(task)
        
        db.session.commit()
        print("示例数据初始化完成！")
        print(f"- 创建了 {len(teachers)} 名教师")
        print(f"- 创建了 {len(tasks)} 个汇总任务")

if __name__ == "__main__":
    init_sample_data()