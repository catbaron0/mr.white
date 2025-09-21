import subprocess
import os
import signal


def find_and_kill(process_name: str):
    """查找并杀掉进程"""
    try:
        # 用 pgrep 找到进程号
        pids = subprocess.check_output(["pgrep", "-f", process_name]).decode().split()
        for pid in pids:
            print(f"终止进程 {pid} ({process_name})")
            os.kill(int(pid), signal.SIGTERM)  # 发送终止信号
    except subprocess.CalledProcessError:
        print(f"没有找到 {process_name} 进程")


def restart():
    find_and_kill("mr.white.py")
    print("重新启动 mr.white.py ...")
    # subprocess.Popen([sys.executable, "mr.white.py"])


if __name__ == "__main__":
    restart()
