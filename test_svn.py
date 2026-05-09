import subprocess
import sys

def test_svn():
    # 尝试不同的 SVN 路径
    svn_paths = [
        "svn",
        r"C:\Program Files\TortoiseSVN\bin\svn.exe",
        r"C:\Program Files (x86)\TortoiseSVN\bin\svn.exe",
        r"C:\Program Files\SlikSvn\bin\svn.exe",
        r"C:\Program Files (x86)\SlikSvn\bin\svn.exe"
    ]
    
    for svn_path in svn_paths:
        try:
            print(f"尝试执行: {svn_path} --version")
            # 使用 shell=True 来避免一些路径问题
            result = subprocess.run(
                f"{svn_path} --version",
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            print(f"返回码: {result.returncode}")
            print(f" stdout: {result.stdout[:200]}...")
            print(f" stderr: {result.stderr[:200]}...")
            if result.returncode == 0:
                print(f"✓ 成功: {svn_path}")
                return True
        except Exception as e:
            print(f"✗ 失败: {svn_path}, 错误: {e}")
    
    print("所有 SVN 路径都失败了")
    return False

if __name__ == "__main__":
    test_svn()
