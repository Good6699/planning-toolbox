# 测试 subprocess 模块中的常量
print("测试 subprocess 常量...")
try:
    print(f"subprocess.STARTF_USESHOWWINDOW = {subprocess.STARTF_USESHOWWINDOW}")
except AttributeError as e:
    print(f"subprocess.STARTF_USESHOWWINDOW 不存在: {e}")

try:
    print(f"subprocess.SW_HIDE = {subprocess.SW_HIDE}")
except AttributeError as e:
    print(f"subprocess.SW_HIDE 不存在: {e}")

try:
    print(f"subprocess.CREATE_NO_WINDOW = {subprocess.CREATE_NO_WINDOW}")
except AttributeError as e:
    print(f"subprocess.CREATE_NO_WINDOW 不存在: {e}")

print("测试完成")
