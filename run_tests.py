"""
Simple test runner for the backend API.
Run with: python run_tests.py
"""
import subprocess
import sys
import os

def run_tests():
    """Run all tests and display results."""
    print("🧪 Running Backend API Tests")
    print("=" * 50)
    
    # Set PYTHONPATH to include current directory
    env = os.environ.copy()
    env['PYTHONPATH'] = os.getcwd()
    
    test_files = [
        'tests/test_address_routes.py',
        'tests/test_cart_routes.py', 
        'tests/test_contact_routes.py',
        'payfastpk/test_payfast_api.py'
    ]
    
    all_passed = True
    
    for test_file in test_files:
        if os.path.exists(test_file):
            print(f"\n📋 Running {test_file}")
            print("-" * 30)
            
            try:
                # Use sys.executable to ensure we use the correct Python interpreter
                result = subprocess.run(
                    [sys.executable, '-m', 'pytest', test_file, '-v'],
                    env=env,
                    capture_output=True,
                    text=True,
                    cwd=os.getcwd()
                )
                
                if result.returncode == 0:
                    print(f"✅ {test_file} - PASSED")
                    if result.stdout.strip():
                        print("Output:")
                        print(result.stdout)
                else:
                    print(f"❌ {test_file} - FAILED")
                    if result.stdout.strip():
                        print("STDOUT:")
                        print(result.stdout)
                    if result.stderr.strip():
                        print("STDERR:")
                        print(result.stderr)
                    all_passed = False
                    
            except Exception as e:
                print(f"⚠️  Error running {test_file}: {e}")
                all_passed = False
        else:
            print(f"⚠️  Test file not found: {test_file}")
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All tests passed!")
        return 0
    else:
        print("💥 Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(run_tests())
