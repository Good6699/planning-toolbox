import sys
import os
import pickle

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    if len(sys.argv) != 3:
        sys.stderr.write(f"Usage: {sys.argv[0]} <arg_pickle> <res_pickle>\n")
        sys.exit(1)

    arg_path, res_path = sys.argv[1], sys.argv[2]

    try:
        with open(arg_path, "rb") as f:
            cur_path, prv_path, cur, prv, fname, tr, id_col, output_cols = pickle.load(f)
    except Exception as e:
        sys.stderr.write(f"[worker] Failed to read args: {e}\n")
        sys.exit(1)

    try:
        with open(cur_path, "rb") as f:
            cur_b = f.read()
        with open(prv_path, "rb") as f:
            prv_b = f.read()
    except Exception as e:
        sys.stderr.write(f"[worker] Failed to read file data: {e}\n")
        sys.exit(1)

    from svn_oneclick_compare import _cmp_task_proc
    result = _cmp_task_proc((cur_b, prv_b, cur, prv, fname, tr, id_col, output_cols))

    with open(res_path, "wb") as f:
        pickle.dump(result, f)

    sys.exit(0)


if __name__ == "__main__":
    main()
