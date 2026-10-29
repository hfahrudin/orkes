# The LangGraph comparison scripts in the sub-folders are run directly
# (see run_all_benchmarks.py), not by pytest. Their *_test.py names would
# otherwise make pytest collect them, and their duplicate basenames clash.
collect_ignore_glob = ["*/*_test.py"]
