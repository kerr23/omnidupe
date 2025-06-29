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
