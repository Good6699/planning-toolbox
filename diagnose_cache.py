"""诊断脚本：测试 worker 进程中是否能写入 __parse_cache__"""
import os
import sys
import pickle
import multiprocessing as mp

# 模拟 worker 中的 __file__
_script_dir = os.path.dirname(os.path.abspath(__file__))
_cache_dir = os.path.join(_script_dir, "__parse_cache")
_cache_test_file = os.path.join(_cache_dir, "__diag_test__.pkl")

def test_in_subprocess():
    """在独立进程中测试"""
    # 检查主进程能否写入
    os.makedirs(_cache_dir, exist_ok=True)
    print(f"主进程 PID={os.getpid()}")
    print(f"缓存目录: {_cache_dir}")
    print(f"缓存目录存在: {os.path.exists(_cache_dir)}")

    try:
        with open(_cache_test_file, "wb") as f:
            pickle.dump({"test": 123}, f, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"主进程写入成功: {os.path.exists(_cache_test_file)}")
        os.remove(_cache_test_file)
    except Exception as e:
        print(f"主进程写入失败: {e}")

    # 测试子进程
    def worker_test(_cd):
        try:
            import os, pickle
            f = os.path.join(_cd, "__worker_test__.pkl")
            with open(f, "wb") as fh:
                pickle.dump({"worker": True}, fh, protocol=pickle.HIGHEST_PROTOCOL)
            return ("成功", f, os.path.exists(f))
        except Exception as e:
            return ("失败", str(e), False)

    with mp.Pool(1) as pool:
        result = pool.apply(worker_test, (_cache_dir,))
    print(f"Worker 测试结果: {result}")

    # 检查 __parse_cache__ 里实际有什么
    if os.path.exists(_cache_dir):
        files = os.listdir(_cache_dir)
        print(f"__parse_cache__ 内容 ({len(files)} 个文件): {files[:5]}")

if __name__ == "__main__":
    test_in_subprocess()
