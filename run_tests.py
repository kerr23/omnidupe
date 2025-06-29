#!/usr/bin/env python3
"""
Test runner script for OmniDupe test suite.
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_tests(test_type="all", coverage=False, verbose=False):
    """Run the test suite with specified options."""
    
    # Base pytest command
    cmd = ["python", "-m", "pytest"]
    
    # Add test selection
    if test_type == "unit":
        cmd.extend(["-m", "unit"])
    elif test_type == "integration":
        cmd.extend(["-m", "integration"])
    elif test_type == "fast":
        cmd.extend(["-m", "not slow"])
    elif test_type != "all":
        # Specific test file or pattern
        cmd.append(test_type)
    
    # Add coverage if requested
    if coverage:
        cmd.extend(["--cov=src", "--cov-report=html", "--cov-report=term"])
    
    # Add verbosity
    if verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")
    
    # Run the tests
    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=Path.cwd())
    return result.returncode


def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(description="Run OmniDupe test suite")
    parser.add_argument(
        "test_type", 
        nargs="?", 
        default="all",
        choices=["all", "unit", "integration", "fast"],
        help="Type of tests to run (default: all)"
    )
    parser.add_argument(
        "--coverage", "-c",
        action="store_true",
        help="Generate coverage report"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--specific", "-s",
        help="Run specific test file or pattern"
    )
    
    args = parser.parse_args()
    
    # Use specific test if provided
    test_type = args.specific if args.specific else args.test_type
    
    exit_code = run_tests(test_type, args.coverage, args.verbose)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
