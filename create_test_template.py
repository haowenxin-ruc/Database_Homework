import pandas as pd

# 创建测试模板
data = {
    '姓名': ['示例：张三'],
    '工号': ['示例：1001'],
    '所在部门': ['示例：计算机学院'],
    '联系电话': ['示例：13800138000'],
    '备注': ['请在此填写备注信息']
}

df = pd.DataFrame(data)
df.to_excel('test_template.xlsx', index=False)
print("测试模板已创建：test_template.xlsx")