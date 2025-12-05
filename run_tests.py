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
        'tests/test_checkout_routes.py',
        'payfastpk/test_payfast_api.py'
    ]
    
    all_passed = True
    total_tests = 0
    passed_tests = 0
    
    for test_file in test_files:
        if os.path.exists(test_file):
            print(f"\n📋 Running {test_file}")
            print("-" * 30)
            
            try:
                # Use sys.executable to ensure we use the correct Python interpreter
                result = subprocess.run(
                    [sys.executable, '-m', 'pytest', test_file, '-v', '--tb=short'],
                    env=env,
                    capture_output=True,
                    text=True,
                    cwd=os.getcwd()
                )
                
                # Count tests from output
                output_lines = result.stdout.split('\n')
                test_count = sum(1 for line in output_lines if '::test_' in line and ('PASSED' in line or 'FAILED' in line))
                failed_count = sum(1 for line in output_lines if '::test_' in line and 'FAILED' in line)
                passed_count = test_count - failed_count
                
                total_tests += test_count
                passed_tests += passed_count
                
                if result.returncode == 0:
                    print(f"✅ {test_file} - PASSED ({passed_count}/{test_count} tests)")
                else:
                    print(f"❌ {test_file} - FAILED ({passed_count}/{test_count} tests)")
                    # Only show failed test details
                    failed_lines = [line for line in output_lines if 'FAILED' in line or 'ERROR' in line]
                    if failed_lines:
                        print("Failed tests:")
                        for line in failed_lines[:5]:  # Limit to first 5 failures
                            print(f"  {line}")
                    all_passed = False
                    
            except Exception as e:
                print(f"⚠️  Error running {test_file}: {e}")
                all_passed = False
        else:
            print(f"⚠️  Test file not found: {test_file}")
            all_passed = False
    
    print("\n" + "=" * 50)
    print(f"📊 Test Summary: {passed_tests}/{total_tests} tests passed")
    
    if all_passed:
        print("🎉 All tests passed!")
        return 0
    else:
        print("💥 Some tests failed!")
        print("\n💡 Run individual tests for more details:")
        for test_file in test_files:
            if os.path.exists(test_file):
                print(f"   python -m pytest {test_file} -v")
        return 1

def run_single_test(test_file):
    """Run a single test file with detailed output."""
    if not os.path.exists(test_file):
        print(f"❌ Test file not found: {test_file}")
        return 1
    
    env = os.environ.copy()
    env['PYTHONPATH'] = os.getcwd()
    
    result = subprocess.run(
        [sys.executable, '-m', 'pytest', test_file, '-v', '-s'],
        env=env,
        cwd=os.getcwd()
    )
    return result.returncode

if __name__ == "__main__":
    # Check if specific test file provided as argument
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
        sys.exit(run_single_test(test_file))
    else:
        sys.exit(run_tests())
