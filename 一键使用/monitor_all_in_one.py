import os
import sys
import time
import configparser
import subprocess

# 把两个监控模块直接编译进 EXE
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import monitor_ashare as ashare
import monitor_global as glob

def get_base_dir():
    """获取 EXE 或脚本所在的目录"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def load_token():
    """从同目录下的 config.ini 加载 Token"""
    base_dir = get_base_dir()
    config_path = os.path.join(base_dir, 'config.ini')
    
    if not os.path.exists(config_path):
        print(f"\n❌ [错误] 找不到配置文件: {config_path}")
        print("💡 请确保同级目录下存在 config.ini 文件。")
        input("按回车键退出...")
        sys.exit(1)
    
    config = configparser.ConfigParser()
    config.read(config_path, encoding='utf-8')
    token = config.get('API_CONFIG', 'TUSHARE_TOKEN').strip('"').strip("'")
    if not token or token == 'YOUR_TUSHARE_TOKEN':
        print(f"\n❌ 请先打开 config.ini 填入你的 Tushare Token！")
        input("按回车键退出...")
        sys.exit(1)
    return token

def run_ashare_mode():
    """A股监控模式"""
    os.system('title 🇨🇳 A股宏观风控终端')
    token = load_token()
    ashare.TS_TOKEN = token
    ashare.main()
    input("按回车键退出...")

def run_global_mode():
    """全球监控模式"""
    os.system('title 🌍 全球宏观周期罗盘')
    glob.main()
    input("按回车键退出...")

def run_launcher():
    """启动器模式：弹出两个独立窗口"""
    print("=" * 50)
    print("📈 宏观金融上帝视角终端 - 启动器")
    print("=" * 50)
    
    # 预检 config.ini
    token = load_token()
    print(f"\n🔑 Token 已从 config.ini 加载成功")
    
    # 获取自身路径（EXE 或 py 脚本）
    if getattr(sys, 'frozen', False):
        self_path = sys.executable
    else:
        self_path = f'"{sys.executable}" "{os.path.abspath(__file__)}"'
    
    # 弹出两个新的 cmd 窗口，分别带不同参数运行自己
    print("\n🌍 正在启动【全球宏观周期罗盘】窗口...")
    subprocess.Popen(f'start "全球宏观" cmd /c "{self_path} --global"', shell=True, cwd=get_base_dir())
    time.sleep(1)
    
    print("🇨🇳 正在启动【A股宏观风控终端】窗口...")
    subprocess.Popen(f'start "A股风控" cmd /c "{self_path} --ashare"', shell=True, cwd=get_base_dir())
    
    print("\n✅ 两个监控终端已在独立窗口中启动！")
    print("   本窗口将在 3 秒后自动关闭...")
    time.sleep(3)

if __name__ == "__main__":
    # 根据命令行参数决定运行模式
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        if mode == '--ashare':
            run_ashare_mode()
        elif mode == '--global':
            run_global_mode()
        else:
            print(f"未知参数: {mode}")
    else:
        # 无参数 = 启动器模式
        run_launcher()
