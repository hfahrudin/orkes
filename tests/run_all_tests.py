import os
import subprocess
import sys

def run_all_tests():
    test_root_dir = os.path.dirname(__file__)  # This will be the 'tests/' directory
    
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
    for folder in test_folders:
        print(f"\nRunning tests in {folder}...")
        result = subprocess.run([sys.executable, "-m", "pytest", folder])
        if result.returncode != 0:
            print(f"Tests in {folder} FAILED.")
            overall_success = False
        else:
            print(f"Tests in {folder} PASSED.")

    if overall_success:
        print("\nAll selected test folders PASSED.")
        sys.exit(0)
    else:
        print("\nSome test folders FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    run_all_tests()
