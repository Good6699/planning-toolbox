# 只使用 Python 标准库，不调用任何外部命令
print("Hello, World!")
print("Python version:")
import sys
print(sys.version)
print("System platform:")
print(sys.platform)
print("Current directory:")
import os
print(os.getcwd())
print("Environment variables:")
print("PATH length:", len(os.environ.get("PATH", "")))
print("Test completed successfully!")
