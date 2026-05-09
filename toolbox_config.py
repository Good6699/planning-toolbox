import os, argparse, json

parser = argparse.ArgumentParser()
parser.add_argument("--dir", type=str, default=None,
                   help="Base directory for output files")
args = parser.parse_args()

# ── 路径配置 ──────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 如果传入了 --dir 参数，覆盖默认路径
if args.dir and os.path.isdir(args.dir):
    SCRIPT_DIR = args.dir

MAIN_SCRIPT = os.path.join(SCRIPT_DIR, "svn_oneclick_compare.py")
CONFIG_FILE = os.path.join(SCRIPT_DIR, "svn_gui_config.json")
DEFAULT_OUTPUT_DIR = os.path.join(SCRIPT_DIR, "输出")  # GUI 同级输出文件夹

# ── 配置读写 ──────────────────────────────────────────────
def load_config():
    default = {
        "svn_urls": [
            "http://192.168.1.41:8080/svn/D3/branches/20240606_KR2/gameData/Text/Texts.xlsm"
        ],
        "cmp_file_presets": []
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 合并默认值
                for k, v in default.items():
                    if k not in data:
                        data[k] = v
                return data
        except json.JSONDecodeError:
            # 配置文件损坏，返回默认值
            print("⚠️ 配置文件损坏，使用默认配置")
            return default
        except Exception as e:
            print(f"⚠️ 加载配置失败: {e}")
            return default
    return default

def save_config(config):
    try:
        # 确保配置目录存在
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ 保存配置失败: {e}")

def int_or(val, default):
    try:
        return int(val)
    except (ValueError, TypeError):
        return default
