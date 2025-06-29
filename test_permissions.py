#!/usr/bin/env python3
"""
Quick test of the permission handling functionality.
"""

import tempfile
from pathlib import Path
from src.file_manager import FileManager

def test_permission_handling():
    """Test that permission checking works."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Test 1: Check write permission method
        fm = FileManager(dry_run=False)
        
        # Create a test file
        test_file = temp_path / "test.jpg"
        test_file.write_text("test content")
        
        # Test permission checking
        has_permission = fm._check_write_permission(test_file)
        print(f"Write permission check for existing file: {has_permission}")
        
        # Test permission for non-existent file
        nonexistent = temp_path / "nonexistent.jpg"
        has_permission_parent = fm._check_write_permission(nonexistent)
        print(f"Write permission check for parent directory: {has_permission_parent}")
        
        # Test 2: Test move with permission checking
        move_dir = temp_path / "moved"
        fm_move = FileManager(dry_run=False, move_to_dir=move_dir)
        
        result = fm_move._move_file_to_directory(test_file, move_dir)
        print(f"Move operation result: {result}")
        print(f"Original file exists: {test_file.exists()}")
        print(f"Moved file exists: {(move_dir / 'test.jpg').exists()}")
        
        print("Permission handling test completed successfully!")

if __name__ == "__main__":
    test_permission_handling()
