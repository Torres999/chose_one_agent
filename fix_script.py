import re
import sys

def fix_indentation(file_path):
    print(f"正在修复文件: {file_path}")
    
    # 读取文件内容
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 第875行左右的修复
    if len(lines) > 875:
        # 修复第875行的缩进
        if "current_url = self.page.url" in lines[874]:
            lines[874] = lines[874].replace("current_url = self.page.url", "                            current_url = self.page.url")
    
    # 第919行左右的修复
    if len(lines) > 919:
        # 修复第919行的缩进
        if "return True" in lines[918]:
            lines[918] = lines[918].replace("                                    return True", "                            return True")
    
    # 第923行左右的修复
    if len(lines) > 923:
        # 修复嵌套的except块
        if "except Exception as e:" in lines[922]:
            lines[922] = lines[922].replace("                        except Exception as e:", "                except Exception as e:")
        
        # 修复logger.error行的缩进
        if len(lines) > 924 and "logger.error" in lines[923]:
            lines[923] = lines[923].replace("                logger.error", "                    logger.error")
    
    # 第963-966行的缩进修复
    if len(lines) > 966:
        if "if js_result:" in lines[962]:
            lines[962] = lines[962].replace("                    if js_result:", "            if js_result:")
        
        # 修复后续几行的缩进
        if "# 等待导航完成" in lines[963]:
            lines[963] = lines[963].replace("                # 等待导航完成", "                # 等待导航完成")
        
        if "self.page.wait_for_load_state" in lines[964]:
            lines[964] = lines[964].replace("                self.page.wait_for_load_state", "                self.page.wait_for_load_state")
        
        if "time.sleep" in lines[965]:
            lines[965] = lines[965].replace("                time.sleep", "                time.sleep")
    
    # 第1005行左右的修复 (if section in ["看盘", ...])
    if len(lines) > 1005:
        if 'if section in ["看盘", "公司", "要闻", "科技"]:' in lines[1004]:
            lines[1004] = lines[1004].replace("                if section in", "                    if section in")
            
        # 修复下一行的缩进
        if len(lines) > 1005 and "return True" in lines[1005]:
            lines[1005] = lines[1005].replace("                return True", "                        return True")
    
    # 保存修复后的文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print(f"文件修复完成！")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        fix_indentation(file_path)
    else:
        print("请提供要修复的文件路径")
        sys.exit(1) 