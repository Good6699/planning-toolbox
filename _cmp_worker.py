import sys, pickle, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import svn_oneclick_compare as svn

try:
    arg_file = sys.argv[1]
    res_file = sys.argv[2]

    with open(arg_file, "rb") as f:
        args = pickle.load(f)

    cur_path, prv_path, cur, prv, fname, tr, id_col, output_cols = args

    with open(cur_path, "rb") as f:
        cur_b = f.read()
    with open(prv_path, "rb") as f:
        prv_b = f.read()

    cmp_args = (cur_b, prv_b, cur, prv, fname, tr, id_col, output_cols)
    result = svn._cmp_task_proc(cmp_args)

    with open(res_file, "wb") as f:
        pickle.dump(result, f)

    sys.exit(0)
except Exception as e:
    sys.stderr.write(f"cmp_worker error: {e}\n")
    sys.exit(1)
