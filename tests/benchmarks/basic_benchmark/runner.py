import subprocess
import json
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import sys

def run_benchmark(script_path):
    """Runs a benchmark script and returns the results."""
    # Convert string path to a platform-aware Path object
    p = Path(script_path)
    
    # Use sys.executable to ensure the same Python interpreter is used
    # shell=True is sometimes needed on Windows for certain PATH resolutions, 
    # but sys.executable usually bypasses that need.
    result = subprocess.run(
        [sys.executable, str(p)],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"Error running {script_path}:\n{result.stderr}")
    
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"Failed to parse JSON from {script_path}. Output: {result.stdout}")


if __name__ == "__main__":
    # Run benchmarks in separate processes
    # Construct paths relative to the current script's directory
    script_dir = Path(__file__).parent
    orkes_benchmark_path = script_dir / 'orkes_test.py'
    langgraph_benchmark_path = script_dir / 'langgraph_test.py'

    orkes_results = run_benchmark(str(orkes_benchmark_path))
    langgraph_results = run_benchmark(str(langgraph_benchmark_path))

    orkes_time = orkes_results['time']
    orkes_mem = orkes_results['memory']
    langgraph_time = langgraph_results['time']
    langgraph_mem = langgraph_results['memory']
    
    # --- Report ---
    print("--- Benchmark Results ---")
    print(f"Execution Time:")
    print(f"  - Orkes:      {orkes_time:.6f} seconds")
    print(f"  - LangGraph:  {langgraph_time:.6f} seconds")
    print(f"\nMemory Usage (Max):")
    print(f"  - Orkes:      {orkes_mem:.2f} MiB")
    print(f"  - LangGraph:  {langgraph_mem:.2f} MiB")
    print("-------------------------")

    # --- Plotting ---
    labels = ['Orkes', 'LangGraph']
    times = [orkes_time, langgraph_time]
    mems = [orkes_mem, langgraph_mem]

    x = np.arange(len(labels))
    width = 0.35

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # Time Plot
    ax1.bar(x, times, width, label='Time', color=['blue', 'orange'])
    ax1.set_ylabel('Execution Time (seconds)')
    ax1.set_title('Execution Time Comparison')
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels)
    ax1.legend()

    # Memory Plot
    ax2.bar(x, mems, width, label='Memory', color=['blue', 'orange'])
    ax2.set_ylabel('Memory Usage (MiB)')
    ax2.set_title('Memory Usage Comparison')
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels)
    ax2.legend()

    fig.tight_layout()
    # Ensure the results directory exists relative to the benchmarks root
    results_dir = script_dir.parent / 'results'
    results_dir.mkdir(exist_ok=True)
    plt.savefig(results_dir / 'basic_benchmark_results.png')
    print(f"\nBenchmark plot saved to '{results_dir / 'basic_benchmark_results.png'}'")