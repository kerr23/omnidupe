"""
Tests for the FileManager module.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from src.file_manager import FileManager
from src.duplicate_detector import DuplicateGroup


class TestFileManager:
    """Test cases for FileManager class."""

    def test_file_manager_init_dry_run(self):
        """Test FileManager initialization with dry run."""
        fm = FileManager(dry_run=True)
        assert fm.dry_run is True

    def test_file_manager_init_normal(self):
        """Test FileManager initialization without dry run."""
        fm = FileManager(dry_run=False)
        assert fm.dry_run is False

    def test_file_manager_init_with_move_dir(self, temp_dir):
        """Test FileManager initialization with move directory."""
        move_dir = temp_dir / "move_to"
        fm = FileManager(dry_run=False, move_to_dir=move_dir)
        assert fm.dry_run is False
        assert fm.move_to_dir == move_dir

    def test_remove_files_from_database_no_files(self, file_manager, memory_db):
        """Test removing files when no files are marked for removal."""
        removed_count = file_manager.remove_files_from_database(memory_db, dry_run=True)
        assert removed_count == 0

    def test_remove_files_from_database_with_files(self, temp_dir, memory_db):
        """Test removing files marked for removal."""
        from src.metadata_extractor import ImageMetadata
        
        # Create test files and metadata
        file1 = temp_dir / "remove1.jpg"
        file2 = temp_dir / "remove2.jpg"
        file1.touch()  # Create actual files
        file2.touch()
        
        metadata1 = ImageMetadata(file1)
        metadata1.file_size = 1000
        metadata1.file_hash = "hash1"
        metadata1.width = 800
        metadata1.height = 600
        
        metadata2 = ImageMetadata(file2)
        metadata2.file_size = 1200
        metadata2.file_hash = "hash2"
        metadata2.width = 900
        metadata2.height = 700
        
        id1 = memory_db.store_image_metadata(file1, metadata1)
        id2 = memory_db.store_image_metadata(file2, metadata2)
        
        # Mark for removal
        memory_db.mark_image_for_removal(id1, "duplicate")
        memory_db.mark_image_for_removal(id2, "similar")
        
        # Test dry run
        fm = FileManager(dry_run=True)
        removed_count = fm.remove_files_from_database(memory_db, dry_run=True)
        assert removed_count == 2
        assert file1.exists()  # Files should still exist in dry run
        assert file2.exists()
        
        # Test actual removal
        fm = FileManager(dry_run=False)
        removed_count = fm.remove_files_from_database(memory_db, dry_run=False)
        assert removed_count == 2
        assert not file1.exists()  # Files should be deleted
        assert not file2.exists()

    def test_remove_files_from_database_missing_file(self, temp_dir, memory_db):
        """Test removing files when file doesn't exist on disk."""
        from src.metadata_extractor import ImageMetadata
        
        # Create metadata for non-existent file
        missing_file = temp_dir / "missing.jpg"
        metadata = ImageMetadata(missing_file)
        metadata.file_size = 1000
        metadata.file_hash = "hash"
        metadata.width = 800
        metadata.height = 600
        
        image_id = memory_db.store_image_metadata(missing_file, metadata)
        memory_db.mark_image_for_removal(image_id, "duplicate")
        
        fm = FileManager(dry_run=False)
        removed_count = fm.remove_files_from_database(memory_db, dry_run=False)
        
        # Should still count as "removed" since file is already gone
        assert removed_count == 1

    def test_get_file_info_existing_file(self, temp_dir):
        """Test getting file info for existing file."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")
        
        fm = FileManager()
        info = fm.get_file_info(test_file)
        
        assert info['exists'] is True
        assert info['is_file'] is True
        assert info['size'] > 0
        assert info['readable'] is True
        assert info['writable'] is True
        assert info['error'] is None

    def test_get_file_info_nonexistent_file(self, temp_dir):
        """Test getting file info for non-existent file."""
        test_file = temp_dir / "nonexistent.txt"
        
        fm = FileManager()
        info = fm.get_file_info(test_file)
        
        assert info['exists'] is False
        assert info['is_file'] is False
        assert info['size'] == 0
        assert info['readable'] is False
        assert info['writable'] is False
        assert info['error'] is None

    def test_remove_duplicates_legacy(self, file_manager):
        """Test legacy remove_duplicates method."""
        # Create mock duplicate groups
        mock_group = Mock()
        mock_group.get_duplicates.return_value = []
        mock_group.to_dict.return_value = {
            'duplicates': [],
            'keeper': {'file_path': '/fake/keeper.jpg'}
        }
        
        duplicate_groups = [mock_group]
        
        removed_count = file_manager.remove_duplicates(duplicate_groups)
        assert removed_count == 0

    def test_verify_keeper_files(self, temp_dir):
        """Test verifying keeper files exist."""
        from src.duplicate_detector import DuplicateGroup
        
        # Create test files
        keeper1 = temp_dir / "keeper1.jpg"
        keeper2 = temp_dir / "keeper2.jpg"
        missing_keeper = temp_dir / "missing.jpg"
        
        keeper1.touch()
        keeper2.touch()
        # missing_keeper intentionally not created
        
        # Create mock duplicate groups
        group1 = Mock()
        group1.to_dict.return_value = {
            'keeper': {'file_path': str(keeper1)}
        }
        
        group2 = Mock()
        group2.to_dict.return_value = {
            'keeper': {'file_path': str(keeper2)}
        }
        
        group3 = Mock()
        group3.to_dict.return_value = {
            'keeper': {'file_path': str(missing_keeper)}
        }
        
        duplicate_groups = [group1, group2, group3]
        
        fm = FileManager()
        results = fm.verify_keeper_files(duplicate_groups)
        
        assert results['total_keepers'] == 3
        assert results['accessible_keepers'] == 2
        assert len(results['missing_keepers']) == 1
        assert str(missing_keeper) in results['missing_keepers']

    def test_create_backup_script(self, temp_dir):
        """Test creating backup removal script."""
        # Create mock duplicate groups
        group1 = Mock()
        group1.type = "hash"
        group1.get_duplicates.return_value = [
            {'file_path': str(temp_dir / 'dup1.jpg')},
            {'file_path': str(temp_dir / 'dup2.jpg')}
        ]
        group1.to_dict.return_value = {
            'keeper': {'file_path': str(temp_dir / 'keeper1.jpg')},
            'duplicates': [
                {'file_path': str(temp_dir / 'dup1.jpg')},
                {'file_path': str(temp_dir / 'dup2.jpg')}
            ]
        }
        
        duplicate_groups = [group1]
        
        fm = FileManager()
        script_path = fm.create_backup_script(duplicate_groups, temp_dir)
        
        assert script_path.exists()
        assert script_path.name == "remove_duplicates.sh"
        
        # Check script content
        content = script_path.read_text()
        assert "#!/bin/bash" in content
        assert "rm -f" in content
        assert str(temp_dir / 'dup1.jpg') in content
        assert str(temp_dir / 'dup2.jpg') in content

    @patch('os.access')
    def test_remove_file_permission_denied(self, mock_access, temp_dir):
        """Test file removal with permission denied."""
        test_file = temp_dir / "test.jpg"
        test_file.touch()
        
        # Mock no write permission
        mock_access.return_value = False
        
        fm = FileManager(dry_run=False)
        success = fm._remove_file(test_file)
        
        assert success is False

    def test_remove_file_dry_run(self, temp_dir):
        """Test file removal in dry run mode."""
        test_file = temp_dir / "test.jpg"
        test_file.touch()
        
        fm = FileManager(dry_run=True)
        success = fm._remove_file(test_file)
        
        assert success is True
        assert test_file.exists()  # File should still exist in dry run

    def test_remove_file_actual(self, temp_dir):
        """Test actual file removal."""
        test_file = temp_dir / "test.jpg"
        test_file.touch()
        
        fm = FileManager(dry_run=False)
        success = fm._remove_file(test_file)
        
        assert success is True
        assert not test_file.exists()  # File should be deleted

    def test_remove_file_nonexistent(self, temp_dir):
        """Test removing non-existent file."""
        test_file = temp_dir / "nonexistent.jpg"
        
        fm = FileManager(dry_run=False)
        success = fm._remove_file(test_file)
        
        assert success is False

    def test_remove_file_directory(self, temp_dir):
        """Test removing directory path."""
        test_dir = temp_dir / "testdir"
        test_dir.mkdir()
        
        fm = FileManager(dry_run=False)
        success = fm._remove_file(test_dir)
        
        assert success is False

    def test_move_file_to_directory_success(self, temp_dir):
        """Test moving a file to a directory successfully."""
        move_dir = temp_dir / "move_destination"
        fm = FileManager(dry_run=False, move_to_dir=move_dir)
        
        # Create test file
        test_file = temp_dir / "test_image.jpg"
        test_file.write_text("test content")
        
        # Move the file
        result = fm._move_file_to_directory(test_file, move_dir)
        
        assert result is True
        assert not test_file.exists()  # Original file should be gone
        moved_file = move_dir / "test_image.jpg"
        assert moved_file.exists()  # File should exist in destination
        assert moved_file.read_text() == "test content"

    def test_move_file_to_directory_name_conflict(self, temp_dir):
        """Test moving a file when name conflict exists."""
        move_dir = temp_dir / "move_destination"
        move_dir.mkdir()
        fm = FileManager(dry_run=False, move_to_dir=move_dir)
        
        # Create existing file in destination
        existing_file = move_dir / "test_image.jpg"
        existing_file.write_text("existing content")
        
        # Create test file to move
        test_file = temp_dir / "test_image.jpg"
        test_file.write_text("new content")
        
        # Move the file
        result = fm._move_file_to_directory(test_file, move_dir)
        
        assert result is True
        assert not test_file.exists()  # Original file should be gone
        assert existing_file.exists()  # Original file should still exist
        assert existing_file.read_text() == "existing content"
        
        # Check renamed file exists (should have timestamp-based name)
        moved_files = [f for f in move_dir.glob("test_image_*.jpg") if f != existing_file]
        assert len(moved_files) == 1
        
        renamed_file = moved_files[0]
        assert renamed_file.exists()
        assert renamed_file.read_text() == "new content"
        
        # Verify naming pattern includes timestamp
        import re
        # Should match pattern like "test_image_1234567890123.jpg" or "test_image_1234567890123_1.jpg"
        pattern = r"test_image_\d{13}(_\d+)?\.jpg"
        assert re.match(pattern, renamed_file.name), f"Filename {renamed_file.name} doesn't match expected pattern"

    def test_move_file_unique_naming_with_timestamp(self, temp_dir):
        """Test unique file naming with timestamp when conflicts exist."""
        move_dir = temp_dir / "move_destination"
        move_dir.mkdir()
        fm = FileManager(dry_run=False, move_to_dir=move_dir)
        
        # Create multiple existing files with similar names
        existing_file = move_dir / "test_image.jpg"
        existing_file.write_text("existing content")
        
        # Create test file to move
        test_file = temp_dir / "test_image.jpg"
        test_file.write_text("new content")
        
        # Move the file
        result = fm._move_file_to_directory(test_file, move_dir)
        
        assert result is True
        assert not test_file.exists()  # Original file should be gone
        assert existing_file.exists()  # Original file should still exist
        assert existing_file.read_text() == "existing content"
        
        # Find the moved file (should have timestamp in name)
        moved_files = [f for f in move_dir.glob("test_image_*.jpg") if f != existing_file]
        assert len(moved_files) == 1
        
        moved_file = moved_files[0]
        assert moved_file.read_text() == "new content"
        
        # Verify naming pattern includes timestamp
        import re
        # Should match pattern like "test_image_1234567890123.jpg" or "test_image_1234567890123_1.jpg"
        pattern = r"test_image_\d{13}(_\d+)?\.jpg"
        assert re.match(pattern, moved_file.name), f"Filename {moved_file.name} doesn't match expected pattern"

    def test_move_file_multiple_conflicts_handling(self, temp_dir):
        """Test handling multiple naming conflicts with timestamp and counter."""
        move_dir = temp_dir / "move_destination"
        move_dir.mkdir()
        fm = FileManager(dry_run=False, move_to_dir=move_dir)
        
        # Create original file
        original_file = move_dir / "conflict.jpg"
        original_file.write_text("original")
        
        # Simulate a timestamp-based conflict by creating a file that might conflict
        import time
        timestamp = int(time.time() * 1000)
        timestamp_file = move_dir / f"conflict_{timestamp}.jpg"
        timestamp_file.write_text("timestamp conflict")
        
        # Create test file to move
        test_file = temp_dir / "conflict.jpg"
        test_file.write_text("new content")
        
        # Move the file
        result = fm._move_file_to_directory(test_file, move_dir)
        
        assert result is True
        assert not test_file.exists()  # Original file should be gone
        
        # Should have created a file with timestamp and possibly counter
        moved_files = [f for f in move_dir.glob("conflict_*.jpg") if f != timestamp_file]
        assert len(moved_files) == 1
        
        moved_file = moved_files[0]
        assert moved_file.read_text() == "new content"
        assert moved_file.name != timestamp_file.name  # Should be different

    def test_remove_files_with_move_dry_run(self, temp_dir, memory_db):
        """Test dry run mode with move functionality."""
        from src.metadata_extractor import ImageMetadata
        
        move_dir = temp_dir / "move_destination"
        fm = FileManager(dry_run=True, move_to_dir=move_dir)
        
        # Create test file and metadata
        test_file = temp_dir / "move_test.jpg"
        test_file.touch()
        
        metadata = ImageMetadata(test_file)
        metadata.file_size = 1000
        metadata.file_hash = "hash1"
        
        # Store in database and mark for removal
        memory_db.store_image_metadata(test_file, metadata)
        memory_db.mark_image_for_removal(1, "duplicate")
        
        # Test dry run
        processed_count = fm.remove_files_from_database(memory_db, dry_run=True)
        
        assert processed_count == 1
        assert test_file.exists()  # File should still exist in dry run
        assert not move_dir.exists()  # Move directory shouldn't be created

    def test_remove_files_with_move_actual(self, temp_dir, memory_db):
        """Test actual move operation."""
        from src.metadata_extractor import ImageMetadata
        
        move_dir = temp_dir / "move_destination"
        fm = FileManager(dry_run=False, move_to_dir=move_dir)
        
        # Create test file and metadata
        test_file = temp_dir / "move_test.jpg"
        test_file.write_text("test image content")
        
        metadata = ImageMetadata(test_file)
        metadata.file_size = 1000
        metadata.file_hash = "hash1"
        
        # Store in database and mark for removal
        memory_db.store_image_metadata(test_file, metadata)
        memory_db.mark_image_for_removal(1, "duplicate")
        
        # Test actual move
        processed_count = fm.remove_files_from_database(memory_db, dry_run=False)
        
        assert processed_count == 1
        assert not test_file.exists()  # Original file should be gone
        moved_file = move_dir / "move_test.jpg"
        assert moved_file.exists()  # File should exist in destination
        assert moved_file.read_text() == "test image content"
        
        # Check database was updated
        images_for_removal = memory_db.get_images_for_removal()
        assert len(images_for_removal) == 0  # Should be unmarked

    def test_check_write_permission_existing_file(self, temp_dir):
        """Test write permission check for existing file."""
        fm = FileManager(dry_run=False)
        
        # Create a test file
        test_file = temp_dir / "test.jpg"
        test_file.write_text("test content")
        
        # Should have write permission
        assert fm._check_write_permission(test_file) is True

    def test_check_write_permission_nonexistent_file(self, temp_dir):
        """Test write permission check for non-existent file."""
        fm = FileManager(dry_run=False)
        
        # Test non-existent file (should check parent directory)
        test_file = temp_dir / "nonexistent.jpg"
        
        # Should have write permission to parent directory
        assert fm._check_write_permission(test_file) is True

    def test_move_file_with_permission_check(self, temp_dir):
        """Test move operation with permission checking."""
        move_dir = temp_dir / "move_destination"
        fm = FileManager(dry_run=False, move_to_dir=move_dir)
        
        # Create test file
        test_file = temp_dir / "test_image.jpg"
        test_file.write_text("test content")
        
        # Move should succeed with proper permissions
        result = fm._move_file_to_directory(test_file, move_dir)
        
        assert result is True
        assert not test_file.exists()  # Original file should be gone
        moved_file = move_dir / "test_image.jpg"
        assert moved_file.exists()  # File should exist in destination

    def test_remove_file_with_permission_check(self, temp_dir):
        """Test remove operation with permission checking."""
        fm = FileManager(dry_run=False)
        
        # Create test file
        test_file = temp_dir / "test.jpg"
        test_file.write_text("test content")
        
        # Remove should succeed
        result = fm._remove_file(test_file)
        
        assert result is True
        assert not test_file.exists()  # File should be deleted
