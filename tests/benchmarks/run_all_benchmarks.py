import os
import subprocess
import sys

def run_all_benchmarks():
    benchmarks_root_dir = os.path.join(os.path.dirname(__file__))
    print(f"Starting benchmark run from: {benchmarks_root_dir}\n")

    benchmark_dirs = [d for d in os.listdir(benchmarks_root_dir) if os.path.isdir(os.path.join(benchmarks_root_dir, d)) and d != "results"]

    for benchmark_dir in benchmark_dirs:
        current_benchmark_path = os.path.join(benchmarks_root_dir, benchmark_dir)
        runner_script_path = os.path.join(current_benchmark_path, "runner.py")

        if os.path.exists(runner_script_path):
            print(f"--- Running benchmark in: {benchmark_dir} ---")
            original_cwd = os.getcwd()
            os.chdir(current_benchmark_path)
            try:
                # Execute the runner.py script
                # Using sys.executable ensures the script runs with the same python interpreter
                # as the one running this orchestrator script.
                result = subprocess.run([sys.executable, "runner.py"], capture_output=True, text=True, check=True)
                print("STDOUT:\n", result.stdout)
                if result.stderr:
                    print("STDERR:\n", result.stderr)
                print(f"--- Finished benchmark in: {benchmark_dir} ---\n")
            except subprocess.CalledProcessError as e:
                print(f"--- Error running benchmark in {benchmark_dir} ---")
                print("STDOUT:\n", e.stdout)
                print("STDERR:\n", e.stderr)
                print(f"Error: {e}\n")
            except FileNotFoundError:
                print(f"--- Error: Python interpreter not found. Please ensure Python is in your PATH. ---\n")
            finally:
                os.chdir(original_cwd) # Change back to original CWD
        else:
            print(f"--- No runner.py found in {benchmark_dir}. Skipping. ---\n")

    print("All benchmarks finished.")

if __name__ == "__main__":
    run_all_benchmarks()
