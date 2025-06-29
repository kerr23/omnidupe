"""
Tests for the Database module.
"""

import pytest
import sqlite3
from pathlib import Path
from datetime import datetime

from src.database import Database
from src.metadata_extractor import ImageMetadata


class TestDatabase:
    """Test cases for Database class."""

    def test_database_creation_persistent(self, temp_dir):
        """Test creating a persistent database."""
        db_path = temp_dir / "test.db"
        db = Database(db_path)
        
        assert db.db_path == db_path
        assert db_path.exists()
        
        # Check tables were created
        cursor = db.connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        expected_tables = ['images', 'duplicate_groups', 'group_images']
        for table in expected_tables:
            assert table in tables
        
        db.close()

    def test_database_creation_memory(self):
        """Test creating an in-memory database."""
        db = Database(None)
        
        assert db.db_path is None
        
        # Check tables were created
        cursor = db.connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        expected_tables = ['images', 'duplicate_groups', 'group_images']
        for table in expected_tables:
            assert table in tables
        
        db.close()

    def test_store_image_metadata(self, memory_db, temp_dir):
        """Test storing image metadata."""
        file_path = temp_dir / "test.jpg"
        metadata = ImageMetadata(file_path)
        metadata.file_size = 1024
        metadata.file_hash = "abcd1234"
        metadata.width = 800
        metadata.height = 600
        metadata.format = "JPEG"
        metadata.camera_make = "Canon"
        metadata.camera_model = "EOS R5"
        metadata.perceptual_hash = "deadbeef"
        
        image_id = memory_db.store_image_metadata(file_path, metadata)
        
        assert isinstance(image_id, int)
        assert image_id > 0
        
        # Verify data was stored
        cursor = memory_db.connection.cursor()
        cursor.execute("SELECT * FROM images WHERE id = ?", (image_id,))
        row = cursor.fetchone()
        
        assert row is not None
        assert row['file_path'] == str(file_path)
        assert row['file_size'] == 1024
        assert row['file_hash'] == "abcd1234"
        assert row['width'] == 800
        assert row['height'] == 600

    def test_get_all_images(self, populated_db):
        """Test retrieving all images."""
        images = populated_db.get_all_images()
        
        assert len(images) == 4
        assert all(isinstance(img['id'], int) for img in images)
        assert all(img['file_path'] for img in images)

    def test_get_images_by_hash(self, memory_db, temp_dir):
        """Test grouping images by hash."""
        # Create two images with same hash
        file1 = temp_dir / "file1.jpg"
        file2 = temp_dir / "file2.jpg"
        file3 = temp_dir / "file3.jpg"
        
        metadata1 = ImageMetadata(file1)
        metadata1.file_hash = "samehash"
        metadata1.file_size = 1000
        metadata1.width = 800
        metadata1.height = 600
        
        metadata2 = ImageMetadata(file2)
        metadata2.file_hash = "samehash"  # Same hash
        metadata2.file_size = 1200
        metadata2.width = 900
        metadata2.height = 700
        
        metadata3 = ImageMetadata(file3)
        metadata3.file_hash = "differenthash"
        metadata3.file_size = 800
        metadata3.width = 600
        metadata3.height = 400
        
        memory_db.store_image_metadata(file1, metadata1)
        memory_db.store_image_metadata(file2, metadata2)
        memory_db.store_image_metadata(file3, metadata3)
        
        groups = memory_db.get_images_by_hash()
        
        assert len(groups) == 1  # Only one group with duplicates
        assert "samehash" in groups
        assert len(groups["samehash"]) == 2

    def test_create_duplicate_group(self, memory_db):
        """Test creating duplicate groups."""
        group_id = memory_db.create_duplicate_group("hash", 0.95)
        
        assert isinstance(group_id, int)
        assert group_id > 0
        
        # Verify group was created
        cursor = memory_db.connection.cursor()
        cursor.execute("SELECT * FROM duplicate_groups WHERE id = ?", (group_id,))
        row = cursor.fetchone()
        
        assert row is not None
        assert row['group_type'] == "hash"
        assert row['similarity_score'] == 0.95

    def test_add_image_to_group(self, memory_db, temp_dir):
        """Test adding images to duplicate groups."""
        # Create image and group
        file_path = temp_dir / "test.jpg"
        metadata = ImageMetadata(file_path)
        metadata.file_size = 1000
        metadata.file_hash = "test"
        metadata.width = 800
        metadata.height = 600
        
        image_id = memory_db.store_image_metadata(file_path, metadata)
        group_id = memory_db.create_duplicate_group("test")
        
        # Add image to group
        memory_db.add_image_to_group(group_id, image_id, is_keeper=True)
        
        # Verify relationship
        cursor = memory_db.connection.cursor()
        cursor.execute("""
            SELECT * FROM group_images 
            WHERE group_id = ? AND image_id = ?
        """, (group_id, image_id))
        row = cursor.fetchone()
        
        assert row is not None
        assert row['is_keeper'] == 1  # SQLite stores boolean as int

    def test_mark_image_for_removal(self, memory_db, temp_dir):
        """Test marking images for removal."""
        file_path = temp_dir / "test.jpg"
        metadata = ImageMetadata(file_path)
        metadata.file_size = 1000
        metadata.file_hash = "test"
        metadata.width = 800
        metadata.height = 600
        
        image_id = memory_db.store_image_metadata(file_path, metadata)
        
        # Mark for removal
        memory_db.mark_image_for_removal(image_id, "duplicate")
        
        # Verify marking
        cursor = memory_db.connection.cursor()
        cursor.execute("SELECT marked_for_removal, removal_reason FROM images WHERE id = ?", (image_id,))
        row = cursor.fetchone()
        
        assert row is not None
        assert row['marked_for_removal'] == 1
        assert row['removal_reason'] == "duplicate"

    def test_mark_image_protected(self, memory_db, temp_dir):
        """Test marking images as protected."""
        file_path = temp_dir / "test.jpg"
        metadata = ImageMetadata(file_path)
        metadata.file_size = 1000
        metadata.file_hash = "test"
        metadata.width = 800
        metadata.height = 600
        
        memory_db.store_image_metadata(file_path, metadata)
        
        # Mark as protected
        success = memory_db.mark_image_protected(str(file_path))
        
        assert success is True
        
        # Verify protection
        cursor = memory_db.connection.cursor()
        cursor.execute("SELECT is_protected FROM images WHERE file_path = ?", (str(file_path),))
        row = cursor.fetchone()
        
        assert row is not None
        assert row['is_protected'] == 1

    def test_mark_image_protected_nonexistent(self, memory_db):
        """Test marking non-existent image as protected."""
        success = memory_db.mark_image_protected("/nonexistent/file.jpg")
        assert success is False

    def test_get_images_for_removal(self, memory_db, temp_dir):
        """Test getting images marked for removal."""
        # Create test images
        file1 = temp_dir / "remove1.jpg"
        file2 = temp_dir / "keep.jpg"
        file3 = temp_dir / "remove2.jpg"
        
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
        
        metadata3 = ImageMetadata(file3)
        metadata3.file_size = 800
        metadata3.file_hash = "hash3"
        metadata3.width = 600
        metadata3.height = 400
        
        id1 = memory_db.store_image_metadata(file1, metadata1)
        id2 = memory_db.store_image_metadata(file2, metadata2)
        id3 = memory_db.store_image_metadata(file3, metadata3)
        
        # Mark some for removal
        memory_db.mark_image_for_removal(id1, "duplicate")
        memory_db.mark_image_for_removal(id3, "similar")
        
        # Get images for removal
        to_remove = memory_db.get_images_for_removal()
        
        assert len(to_remove) == 2
        removal_paths = [img['file_path'] for img in to_remove]
        assert str(file1) in removal_paths
        assert str(file3) in removal_paths
        assert str(file2) not in removal_paths

    def test_protected_image_not_marked_for_removal(self, memory_db, temp_dir):
        """Test that protected images are not marked for removal."""
        file_path = temp_dir / "protected.jpg"
        metadata = ImageMetadata(file_path)
        metadata.file_size = 1000
        metadata.file_hash = "test"
        metadata.width = 800
        metadata.height = 600
        
        image_id = memory_db.store_image_metadata(file_path, metadata)
        
        # Protect the image first
        memory_db.mark_image_protected(str(file_path))
        
        # Try to mark for removal
        memory_db.mark_image_for_removal(image_id, "duplicate")
        
        # Should not be marked for removal
        to_remove = memory_db.get_images_for_removal()
        assert len(to_remove) == 0

    def test_unmark_image_for_removal(self, memory_db, temp_dir):
        """Test unmarking images for removal."""
        file_path = temp_dir / "test.jpg"
        metadata = ImageMetadata(file_path)
        metadata.file_size = 1000
        metadata.file_hash = "test"
        metadata.width = 800
        metadata.height = 600
        
        image_id = memory_db.store_image_metadata(file_path, metadata)
        
        # Mark for removal then unmark
        memory_db.mark_image_for_removal(image_id, "duplicate")
        memory_db.unmark_image_for_removal(image_id)
        
        # Should not be in removal list
        to_remove = memory_db.get_images_for_removal()
        assert len(to_remove) == 0

    def test_get_statistics(self, populated_db):
        """Test getting database statistics."""
        stats = populated_db.get_statistics()
        
        assert 'total_images' in stats
        assert 'images_with_timestamps' in stats
        assert 'images_with_perceptual_hashes' in stats
        assert 'duplicate_groups' in stats
        assert 'groups_by_type' in stats
        
        assert stats['total_images'] == 4
        assert isinstance(stats['total_images'], int)

    def test_database_close(self, temp_dir):
        """Test database connection closing."""
        db_path = temp_dir / "test.db"
        db = Database(db_path)
        
        # Database should be connected
        assert db.connection is not None
        
        db.close()
        
        # Connection should be closed (this will raise an exception if used)
        with pytest.raises(sqlite3.ProgrammingError):
            db.connection.execute("SELECT 1")
