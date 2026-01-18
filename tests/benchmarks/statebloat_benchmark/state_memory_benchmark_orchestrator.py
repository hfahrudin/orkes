import subprocess
import json
import matplotlib.pyplot as plt
from pathlib import Path
import sys
import numpy as np

"""
The state_memory_benchmark_orchestrator.py script coordinates memory and execution time benchmarks for graph processing frameworks like Orkes   
  and Langgraph as their state grows. Its core functions are to run each framework's benchmark in an isolated Python subprocess, collect their    
  JSON outputs, consolidate and summarize these results, and finally, visualize the memory usage and execution time trends through plots.

  How it works:

   1. Imports: It imports necessary modules for subprocess management (subprocess), JSON parsing (json), plotting (matplotlib.pyplot, numpy,      
      pathlib.Path), and system utilities (sys).
   2. `run_benchmark_subprocess(script_path)` function: This helper executes an individual benchmark script. It uses subprocess.run to start a new      Python process, captures its stdout and stderr, and attempts to parse the stdout as JSON. Crucially, check=True ensures it raises an error  
      if the subprocess fails, and sys.executable guarantees the correct Python interpreter is used. It includes error handling for invalid JSON  
      output.
   3. Main Execution (`if __name__ == "__main__":` block):
       * Initialization: It prints a start message and defines the file paths for the individual Orkes and Langgraph benchmark scripts.
       * Benchmark Execution: It sequentially calls run_benchmark_subprocess for both the Orkes and Langgraph scripts, storing their respective   
         JSON outputs in orkes_results and langgraph_results.
       * Data Extraction: It processes the collected JSON data, extracting lists for state_size, memory_mb, and execution_time_ms for each        
         framework's iterations.
       * Summary Report: It prints a formatted summary table displaying the iteration, state size, memory, and execution time for every step of   
         both benchmarks.
       * Plotting:
           * It sets up a matplotlib figure with two subplots.
           * Memory Plot: The first subplot visualizes memory_mb against state_size for both frameworks, including titles, labels, a grid, and a  
             legend.
           * Execution Time Plot: The second subplot similarly plots execution_time_ms against state_size for both frameworks.
           * plt.tight_layout() adjusts the plot layout.
           * Saving Plot: It ensures a results directory exists, then saves the combined plot as state_memory_and_time_benchmark.png within that  
             directory, confirming the save path.

  In summary, the orchestrator streamlines benchmark execution, data aggregation, and visualization, allowing each framework's benchmark to run in  isolation and produce structured, comparable results.

"""

def run_benchmark_subprocess(script_path):
    """Runs a benchmark script as a subprocess and returns the parsed JSON results."""
    p = Path(script_path)
    result = subprocess.run(
        [sys.executable, str(p)],
        capture_output=True,
        text=True,
        check=True # Raise an exception for non-zero exit codes
    )
    
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"Error parsing JSON from {script_path}. Output:\n{result.stdout}", file=sys.stderr)
        raise

if __name__ == "__main__":
    print("Starting State Memory Benchmarks Orchestrator...")

    orkes_benchmark_file = 'tests/benchmarks/orkes_state_memory_benchmark.py'
    langgraph_benchmark_file = 'tests/benchmarks/langgraph_state_memory_benchmark.py'

    # Run Orkes benchmark
    print(f"Running Orkes benchmark: {orkes_benchmark_file}")
    orkes_results = run_benchmark_subprocess(orkes_benchmark_file)
    print("Orkes benchmark finished.")
    
    # Run Langgraph benchmark
    print(f"Running Langgraph benchmark: {langgraph_benchmark_file}")
    langgraph_results = run_benchmark_subprocess(langgraph_benchmark_file)
    print("Langgraph benchmark finished.")

    # Extract data for plotting
    orkes_data = orkes_results['orkes_memory_benchmark']
    langgraph_data = langgraph_results['langgraph_memory_benchmark']

    orkes_state_sizes = [d['state_size'] for d in orkes_data]
    orkes_memory_mb = [d['memory_mb'] for d in orkes_data]
    orkes_execution_time_ms = [d['execution_time_ms'] for d in orkes_data]

    langgraph_state_sizes = [d['state_size'] for d in langgraph_data]
    langgraph_memory_mb = [d['memory_mb'] for d in langgraph_data]
    langgraph_execution_time_ms = [d['execution_time_ms'] for d in langgraph_data]

    # --- Report ---
    print("\n--- State Memory Benchmark Results Summary ---")
    print("Orkes Memory Results:")
    for res in orkes_data:
        print(f"  Iteration: {res['iteration']}, State Size: {res['state_size']}, Memory: {res['memory_mb']:.2f} MiB, Time: {res['execution_time_ms']:.3f} ms")
    
    print("\nLanggraph Memory Results:")
    for res in langgraph_data:
        print(f"  Iteration: {res['iteration']}, State Size: {res['state_size']}, Memory: {res['memory_mb']:.2f} MiB, Time: {res['execution_time_ms']:.3f} ms")
    print("--------------------------------------------")

    # --- Plotting ---
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

    # Memory Plot
    ax1.plot(orkes_state_sizes, orkes_memory_mb, marker='o', label='Orkes')
    ax1.plot(langgraph_state_sizes, langgraph_memory_mb, marker='x', label='Langgraph')
    ax1.set_title('Memory Consumption vs. State Size Growth')
    ax1.set_xlabel('State Size (Number of Key-Value Pairs)')
    ax1.set_ylabel('Memory Usage (MiB)')
    ax1.grid(True)
    ax1.legend()

    # Execution Time Plot
    ax2.plot(orkes_state_sizes, orkes_execution_time_ms, marker='o', label='Orkes')
    ax2.plot(langgraph_state_sizes, langgraph_execution_time_ms, marker='x', label='Langgraph')
    ax2.set_title('Execution Time vs. State Size Growth')
    ax2.set_xlabel('State Size (Number of Key-Value Pairs)')
    ax2.set_ylabel('Execution Time (ms)')
    ax2.grid(True)
    ax2.legend()
    
    plt.tight_layout()
    
    results_dir = Path('tests/benchmarks/results')
    results_dir.mkdir(parents=True, exist_ok=True)
    plot_path = results_dir / 'state_memory_and_time_benchmark.png'
    plt.savefig(plot_path)
    print(f"\nBenchmark plot saved to '{plot_path}'")
