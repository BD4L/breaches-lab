#!/usr/bin/env python3
"""
Debug script for testing database change tracker functionality.
This can be used to test the database change detection logic.
"""

import os
import sys
import json
from datetime import datetime

# Add the scrapers directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'scrapers'))

def test_database_connection():
    """Test basic database connectivity."""
    print("Testing database connection...")
    
    try:
        from scrapers.database_change_tracker import get_database_stats
        
        stats = get_database_stats()
        if stats:
            print("Database connection successful!")
            print(f"Current stats: {stats['total_items']} items, {stats['breach_count']} breaches, {stats['news_count']} news")
            
            # Show source type breakdown
            print("\n Source Type Breakdown:")
            for source_type, count in sorted(stats['by_source_type'].items(), key=lambda x: x[1], reverse=True):
                print(f"   {source_type}: {count}")
            
            return True
        else:
            print("Failed to get database stats")
            return False
            
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False

def test_snapshot_and_report():
    """Test the full snapshot and report cycle."""
    print("\n Testing snapshot and report cycle...")
    
    try:
        from scrapers.database_change_tracker import take_snapshot, generate_report
        
        # Set a test snapshot file
        test_snapshot_file = '/tmp/test_scraper_snapshot.json'
        os.environ['SNAPSHOT_FILE'] = test_snapshot_file
        
        print("Taking test snapshot...")
        if take_snapshot():
            print("Snapshot taken successfully")
            
            # Wait a moment and take another snapshot to test reporting
            print("Waiting 2 seconds...")
            import time
            time.sleep(2)
            
            print("Generating test report...")
            if generate_report():
                print("Report generated successfully")
                return True
            else:
                print("Report generation failed")
                return False
        else:
            print("Snapshot failed")
            return False
            
    except Exception as e:
        print(f"Snapshot/report test failed: {e}")
        return False
    finally:
        # Clean up test file
        if os.path.exists(test_snapshot_file):
            os.remove(test_snapshot_file)

def test_github_output_format():
    """Test GitHub Actions output format."""
    print("\n Testing GitHub Actions output format...")
    
    try:
        # Simulate GitHub Actions environment
        os.environ['GITHUB_ACTIONS'] = 'true'
        test_output_file = '/tmp/test_github_output.txt'
        os.environ['GITHUB_OUTPUT'] = test_output_file
        
        from scrapers.database_change_tracker import generate_report
        
        # Clean up any existing file
        if os.path.exists(test_output_file):
            os.remove(test_output_file)
        
        print("Testing GitHub output generation...")
        generate_report()
        
        if os.path.exists(test_output_file):
            with open(test_output_file, 'r') as f:
                content = f.read()
            print("GitHub output file created:")
            print(content)
            
            # Validate format
            lines = content.strip().split('\n')
            expected_outputs = ['new_items', 'new_breaches', 'new_news', 'new_affected']
            
            for expected in expected_outputs:
                found = any(line.startswith(f"{expected}=") for line in lines)
                if found:
                    print(f"{expected} output found")
                else:
                    print(f"{expected} output missing")
            
            return True
        else:
            print("GitHub output file not created")
            return False
            
    except Exception as e:
        print(f"GitHub output test failed: {e}")
        return False
    finally:
        # Clean up
        if os.path.exists(test_output_file):
            os.remove(test_output_file)
        # Remove GitHub environment
        if 'GITHUB_ACTIONS' in os.environ:
            del os.environ['GITHUB_ACTIONS']
        if 'GITHUB_OUTPUT' in os.environ:
            del os.environ['GITHUB_OUTPUT']

def main():
    """Run all tests."""
    print("DATABASE CHANGE TRACKER DEBUG TESTS")
    print("=" * 50)
    
    tests = [
        ("Database Connection", test_database_connection),
        ("Snapshot & Report Cycle", test_snapshot_and_report),
        ("GitHub Output Format", test_github_output_format),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n Running: {test_name}")
        print("-" * 30)
        success = test_func()
        results.append((test_name, success))
    
    print("\n" + "=" * 50)
    print("TEST RESULTS SUMMARY")
    print("=" * 50)
    
    all_passed = True
    for test_name, success in results:
        status ="PASS"if success else"FAIL"
        print(f"{status}: {test_name}")
        if not success:
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("ALL TESTS PASSED! Database change tracker is working correctly.")
    else:
        print("SOME TESTS FAILED. Check the output above for details.")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())