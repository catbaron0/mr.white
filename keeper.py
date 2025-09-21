import subprocess
import time
import sys

while True:
    try:
        print("启动 mr.white.py ...")
        process = subprocess.Popen(["python", "mr.white.py"])
        process.wait()
    except KeyboardInterrupt:
        print("检测到 Ctrl+C，是否退出守护脚本？(y/n)")
        ans = input().strip().lower()
        if ans == "y":
            print("退出守护脚本")
            process.terminate()
            sys.exit(0)
        else:
            print("继续重启 mr.white.py")
            process.terminate()
            time.sleep(1)
            continue

    print("mr.white.py 已退出，1 秒后重启...")
    time.sleep(1)
