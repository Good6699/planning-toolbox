#!/usr/bin/env python3
# 测试优化后的功能

import sys
import os

# 添加当前目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from svn_oneclick_compare import _parse_excel_lxml, _compare_pair, write_excel

# 测试数据
# 这里我们模拟两个版本的解析结果，用于测试对比功能
def test_compare_pair():
    """测试 _compare_pair 函数的sheet对比功能"""
    # 模拟当前版本的解析结果
    cur_parsed = {
        "sheets": {
            "Sheet1": {
                "map": {
                    "1": {
                        "sc": "SC1",
                        "sheet": "Sheet1",
                        "sub": "Sub1",
                        "cells": {"A": "Value1", "B": "Value2"}
                    },
                    "2": {
                        "sc": "SC2",
                        "sheet": "Sheet1",
                        "sub": "Sub2",
                        "cells": {"A": "Value3", "B": "Value4"}
                    }
                }
            },
            "Sheet2": {
                "map": {
                    "3": {
                        "sc": "SC3",
                        "sheet": "Sheet2",
                        "sub": "Sub3",
                        "cells": {"A": "Value5", "B": "Value6"}
                    }
                }
            }
        },
        "map": {
            "1": {
                "sc": "SC1",
                "sheet": "Sheet1",
                "sub": "Sub1",
                "cells": {"A": "Value1", "B": "Value2"}
            },
            "2": {
                "sc": "SC2",
                "sheet": "Sheet1",
                "sub": "Sub2",
                "cells": {"A": "Value3", "B": "Value4"}
            },
            "3": {
                "sc": "SC3",
                "sheet": "Sheet2",
                "sub": "Sub3",
                "cells": {"A": "Value5", "B": "Value6"}
            }
        }
    }
    
    # 模拟前一版本的解析结果
    prv_parsed = {
        "sheets": {
            "Sheet1": {
                "map": {
                    "1": {
                        "sc": "SC1",
                        "sheet": "Sheet1",
                        "sub": "Sub1",
                        "cells": {"A": "Value1", "B": "Value2"}
                    },
                    "2": {
                        "sc": "SC2",
                        "sheet": "Sheet1",
                        "sub": "Sub2",
                        "cells": {"A": "Value3", "B": "Value7"}  # 修改了B列的值
                    }
                }
            },
            "Sheet3": {
                "map": {
                    "4": {
                        "sc": "SC4",
                        "sheet": "Sheet3",
                        "sub": "Sub4",
                        "cells": {"A": "Value8", "B": "Value9"}
                    }
                }
            }
        },
        "map": {
            "1": {
                "sc": "SC1",
                "sheet": "Sheet1",
                "sub": "Sub1",
                "cells": {"A": "Value1", "B": "Value2"}
            },
            "2": {
                "sc": "SC2",
                "sheet": "Sheet1",
                "sub": "Sub2",
                "cells": {"A": "Value3", "B": "Value7"}
            },
            "4": {
                "sc": "SC4",
                "sheet": "Sheet3",
                "sub": "Sub4",
                "cells": {"A": "Value8", "B": "Value9"}
            }
        }
    }
    
    # 测试对比功能
    results = _compare_pair(100, 99, cur_parsed, prv_parsed, output_cols=["A", "B"])
    print(f"对比结果数量: {len(results)}")
    for i, result in enumerate(results):
        print(f"结果 {i+1}: {result}")
    
    # 测试输出功能
    output_path = "test_output.xlsx"
    write_excel(results, output_path, output_cols=["A", "B"])
    print(f"输出文件已生成: {output_path}")
    
    # 验证输出文件是否存在
    if os.path.exists(output_path):
        print("测试成功: 输出文件已生成")
    else:
        print("测试失败: 输出文件未生成")

if __name__ == "__main__":
    test_compare_pair()
