import os
import subprocess
import sys
from datetime import datetime

# To execute: `python tests/run_all_tests.py`

def run_all_tests():
    # 1. Setup paths
    test_root_dir = os.path.dirname(os.path.abspath(__file__))
    reports_dir = os.path.join(test_root_dir, "reports")
    
    # 2. Create reports directory if it doesn't exist
    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir)
        print(f"Created reports directory: {reports_dir}")

    test_folders = []
    for item in os.listdir(test_root_dir):
        full_path = os.path.join(test_root_dir, item)
        if os.path.isdir(full_path) and (item == "integration_test" or item.endswith("_test")):
            test_folders.append(full_path)

    if not test_folders:
        print("No test folders found matching 'integration_test' or ending with '_test'.")
        sys.exit(0)

    print(f"Found test folders: {test_folders}")
    
    overall_success = True
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for folder in test_folders:
        folder_name = os.path.basename(folder)
        report_path = os.path.join(reports_dir, f"report_{folder_name}_{timestamp}.html")
        
        print(f"\nRunning tests in {folder}...")
        print(f"Report will be saved to: {report_path}")

        # 3. Added Pytest HTML report flags
        # --self-contained-html makes it easy to open the file anywhere
        cmd = [
            sys.executable, "-m", "pytest", 
            folder, 
            f"--html={report_path}", 
            "--self-contained-html"
        ]
        
        result = subprocess.run(cmd)

        if os.path.exists(report_path):
            with open(report_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Remove the problematic line
            content = content.replace("window.history.pushState({}, null, unescape(url.href))", "")

            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(content)

        if result.returncode != 0:
            print(f"Tests in {folder} FAILED.")
            overall_success = False
        else:
            print(f"Tests in {folder} PASSED.")

    # 4. Final Summary
    if overall_success:
        print(f"\nAll tests PASSED. Reports available in: {reports_dir}")
        sys.exit(0)
    else:
        print(f"\nSome tests FAILED. Check reports in: {reports_dir}")
        sys.exit(1)

if __name__ == "__main__":
    run_all_tests()
