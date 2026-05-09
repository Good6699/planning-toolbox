# 测试基本导入
print("开始测试...")
try:
    import sys
    print(f"Python版本: {sys.version}")
    print("sys 导入成功")
except Exception as e:
    print(f"sys 导入失败: {e}")

try:
    import os
    print("os 导入成功")
except Exception as e:
    print(f"os 导入失败: {e}")

try:
    import tempfile
    print("tempfile 导入成功")
    # 测试 tempfile.mkstemp
    import os
    fd, path = tempfile.mkstemp(suffix='.bin')
    print(f"mkstemp 成功: {path}")
    with os.fdopen(fd, 'wb') as f:
        f.write(b"test data")
    print("写入成功")
    os.unlink(path)
    print("删除成功")
except Exception as e:
    print(f"tempfile 测试失败: {e}")

try:
    import subprocess
    print("subprocess 导入成功")
except Exception as e:
    print(f"subprocess 导入失败: {e}")

print("测试完成")
