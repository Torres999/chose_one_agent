#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多股票回测优化器
支持输入多个股票代码，为每个股票代码新开终端窗口执行回测优化命令
支持命令行参数：python multi_stock_backtest.py --symbol 300236,688256,300870...
"""

import subprocess
import sys
import os
from datetime import datetime
import platform
import argparse

def get_current_date():
    """获取当前日期，格式为 YYYY-MM-DD"""
    return datetime.now().strftime("%Y-%m-%d")

def open_terminal_for_stock(symbol, start_date, end_date):
    """
    为指定股票代码新开终端窗口并执行回测优化命令
    
    Args:
        symbol (str): 股票代码
        start_date (str): 开始日期
        end_date (str): 结束日期
    """
    # 构建回测优化命令，使用相对路径
    backtest_script_path = "../backtrade/backtest_optimizer.py"
    command = [
        "python", backtest_script_path,
        "--symbol", symbol,
        "--start", start_date,
        "--end", end_date,
        "--use-baostock",
        "--strategy", "1",
        "--min-threshold", "0.1",
        "--max-threshold", "2",
        "--step", "0.1"
    ]
    
    # 根据操作系统选择不同的终端命令
    system = platform.system()
    
    try:
        if system == "Darwin":  # macOS
            # 使用 osascript 在 macOS 上打开新的 Terminal 窗口
            # 切换到正确的目录并执行命令
            apple_script = f'''
            tell application "Terminal"
                do script "cd '{os.path.dirname(os.path.abspath(__file__))}/../backtrade' && {' '.join(command)}"
            end tell
            '''
            subprocess.run(["osascript", "-e", apple_script], check=True)
            print(f"✅ 已为股票 {symbol} 打开新的终端窗口")
            
        elif system == "Linux":
            # 在 Linux 上使用 gnome-terminal 或其他终端模拟器
            try:
                subprocess.run(["gnome-terminal", "--", "bash", "-c", f"cd {os.path.dirname(os.path.abspath(__file__))}/../backtrade && {' '.join(command)}"], check=True)
                print(f"✅ 已为股票 {symbol} 打开新的终端窗口")
            except FileNotFoundError:
                try:
                    subprocess.run(["konsole", "-e", f"bash -c 'cd {os.path.dirname(os.path.abspath(__file__))}/../backtrade && {' '.join(command)}'"], check=True)
                    print(f"✅ 已为股票 {symbol} 打开新的终端窗口")
                except FileNotFoundError:
                    subprocess.run(["xterm", "-e", f"bash -c 'cd {os.path.dirname(os.path.abspath(__file__))}/../backtrade && {' '.join(command)}'"], check=True)
                    print(f"✅ 已为股票 {symbol} 打开新的终端窗口")
                    
        elif system == "Windows":
            # 在 Windows 上使用 start 命令打开新的命令提示符窗口
            cmd_command = f'cd /d "{os.path.dirname(os.path.abspath(__file__))}\\..\\backtrade" && {" ".join(command)}'
            subprocess.run(["start", "cmd", "/k", cmd_command], shell=True, check=True)
            print(f"✅ 已为股票 {symbol} 打开新的终端窗口")
            
        else:
            print(f"❌ 不支持的操作系统: {system}")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"❌ 为股票 {symbol} 打开终端窗口失败: {e}")
        return False
    
    return True

def process_stock_symbols(symbols, start_date, end_date):
    """
    处理股票代码列表，为每个股票代码打开终端窗口
    
    Args:
        symbols (list): 股票代码列表
        start_date (str): 开始日期
        end_date (str): 结束日期
    """
    print(f"\n📊 准备为以下 {len(symbols)} 个股票代码执行回测优化:")
    for i, symbol in enumerate(symbols, 1):
        print(f"  {i}. {symbol}")
    
    print(f"\n🚀 开始执行回测优化...")
    
    # 为每个股票代码打开新的终端窗口
    success_count = 0
    for symbol in symbols:
        print(f"正在为股票 {symbol} 打开终端窗口...")
        if open_terminal_for_stock(symbol, start_date, end_date):
            success_count += 1
        print()
    
    print(f"✅ 成功为 {success_count}/{len(symbols)} 个股票代码打开终端窗口")
    return success_count

def interactive_mode():
    """交互模式：通过用户输入获取股票代码"""
    print("🚀 多股票回测优化器 - 交互模式")
    print("=" * 50)
    
    # 获取当前日期作为结束日期
    end_date = get_current_date()
    start_date = "2023-01-01"
    
    print(f"📅 回测时间范围: {start_date} 到 {end_date}")
    print()
    
    while True:
        # 获取用户输入的股票代码
        print("请输入股票代码（多个股票代码用空格分隔，输入 'quit' 退出）:")
        user_input = input("股票代码: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("👋 程序退出")
            break
        
        if not user_input:
            print("❌ 请输入有效的股票代码")
            continue
        
        # 分割股票代码
        symbols = [symbol.strip().upper() for symbol in user_input.split() if symbol.strip()]
        
        if not symbols:
            print("❌ 没有找到有效的股票代码")
            continue
        
        # 确认执行
        confirm = input(f"\n确认执行回测优化？(y/n): ").strip().lower()
        if confirm not in ['y', 'yes', '是']:
            print("❌ 已取消执行")
            continue
        
        process_stock_symbols(symbols, start_date, end_date)
        print("=" * 50)
        print()

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='多股票回测优化器')
    parser.add_argument('--symbol', type=str, help='股票代码列表，用逗号分隔（如：300236,688256,300870）')
    parser.add_argument('--start', type=str, default='2023-01-01', help='开始日期（默认：2023-01-01）')
    parser.add_argument('--end', type=str, help='结束日期（默认：当前日期）')
    
    args = parser.parse_args()
    
    # 获取日期
    start_date = args.start
    end_date = args.end if args.end else get_current_date()
    
    if args.symbol:
        # 命令行模式：处理通过--symbol参数传入的股票代码
        symbols = [symbol.strip().upper() for symbol in args.symbol.split(',') if symbol.strip()]
        
        if not symbols:
            print("❌ 没有找到有效的股票代码")
            return
        
        print("🚀 多股票回测优化器 - 命令行模式")
        print("=" * 50)
        print(f"📅 回测时间范围: {start_date} 到 {end_date}")
        
        process_stock_symbols(symbols, start_date, end_date)
        
    else:
        # 交互模式：通过用户输入获取股票代码
        interactive_mode()

if __name__ == "__main__":
    main()
