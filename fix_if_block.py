import re

file_path = 'chose_one_agent/modules/telegraph/base_telegraph_scraper.py'

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

if_line_found = False
return_line_found = False

for i, line in enumerate(lines):
    if '# 如果是已知的板块' in line:
        if_line_found = True
    elif if_line_found and 'if section in ["看盘"' in line:
        print(f"找到if行: {line.strip()}")
        # 保持if行的缩进
    elif if_line_found and 'return True' in line:
        print(f"找到return行: {line.strip()}")
        # 修改return行的缩进
        lines[i] = ' ' * 20 + 'return True\n'  # 20个空格的缩进
        return_line_found = True
        break

if if_line_found and return_line_found:
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print("成功修复文件！")
else:
    print("未找到需要修复的行") 