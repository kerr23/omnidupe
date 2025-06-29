"""
Tests for the DuplicateDetector module.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock

from src.duplicate_detector import DuplicateDetector, DuplicateGroup


class TestDuplicateGroup:
    """Test cases for DuplicateGroup class."""

    def test_duplicate_group_init(self):
        """Test DuplicateGroup initialization."""
        group = DuplicateGroup("hash", 0.95)
        
        assert group.type == "hash"
        assert group.similarity_score == 0.95
        assert group.images == []
        assert group.keeper is None

    def test_add_image(self):
        """Test adding images to group."""
        group = DuplicateGroup("hash")
        
        image1 = {
            'id': 1,
            'file_path': '/test/image1.jpg',
            'file_size': 1000,
            'width': 800,
            'height': 600
        }
        
        image2 = {
            'id': 2,
            'file_path': '/test/image2.jpg',
            'file_size': 1200,
            'width': 900,
            'height': 700
        }
        
        group.add_image(image1)
        group.add_image(image2)
        
        assert len(group.images) == 2
        assert image1 in group.images
        assert image2 in group.images

    def test_select_keeper_highest_resolution(self):
        """Test keeper selection based on highest resolution."""
        group = DuplicateGroup("hash")
        
        image1 = {
            'id': 1,
            'file_path': '/test/image1.jpg',
            'file_size': 1000,
            'width': 800,
            'height': 600  # 480k pixels
        }
        
        image2 = {
            'id': 2,
            'file_path': '/test/image2.jpg',
            'file_size': 1200,
            'width': 1000,
            'height': 800  # 800k pixels (higher)
        }
        
        group.add_image(image1)
        group.add_image(image2)
        
        keeper = group.select_keeper()
        
        assert keeper == image2  # Higher resolution
        assert group.keeper == image2

    def test_select_keeper_same_resolution_larger_size(self):
        """Test keeper selection based on file size when resolution is same."""
        group = DuplicateGroup("hash")
        
        image1 = {
            'id': 1,
            'file_path': '/test/image1.jpg',
            'file_size': 1000,
            'width': 800,
            'height': 600
        }
        
        image2 = {
            'id': 2,
            'file_path': '/test/image2.jpg',
            'file_size': 1500,  # Larger file size
            'width': 800,
            'height': 600
        }
        
        group.add_image(image1)
        group.add_image(image2)
        
        keeper = group.select_keeper()
        
        assert keeper == image2  # Larger file size
        assert group.keeper == image2

    def test_select_keeper_same_resolution_and_size_simpler_name(self):
        """Test keeper selection based on filename when resolution and size are same."""
        group = DuplicateGroup("hash")
        
        image1 = {
            'id': 1,
            'file_path': '/test/very_long_filename.jpg',  # Longer name
            'file_size': 1000,
            'width': 800,
            'height': 600
        }
        
        image2 = {
            'id': 2,
            'file_path': '/test/short.jpg',  # Shorter name
            'file_size': 1000,
            'width': 800,
            'height': 600
        }
        
        group.add_image(image1)
        group.add_image(image2)
        
        keeper = group.select_keeper()
        
        assert keeper == image2  # Simpler (shorter) name
        assert group.keeper == image2

    def test_select_keeper_single_image(self):
        """Test keeper selection with single image."""
        group = DuplicateGroup("hash")
        
        image1 = {
            'id': 1,
            'file_path': '/test/image1.jpg',
            'file_size': 1000,
            'width': 800,
            'height': 600
        }
        
        group.add_image(image1)
        keeper = group.select_keeper()
        
        assert keeper == image1
        assert group.keeper == image1

    def test_select_keeper_no_images(self):
        """Test keeper selection with no images."""
        group = DuplicateGroup("hash")
        keeper = group.select_keeper()
        
        assert keeper is None
        assert group.keeper is None

    def test_get_duplicates(self):
        """Test getting duplicate images (non-keepers)."""
        group = DuplicateGroup("hash")
        
        image1 = {
            'id': 1,
            'file_path': '/test/image1.jpg',
            'file_size': 1000,
            'width': 800,
            'height': 600
        }
        
        image2 = {
            'id': 2,
            'file_path': '/test/image2.jpg',
            'file_size': 1200,
            'width': 1000,
            'height': 800  # This should be keeper (higher resolution)
        }
        
        image3 = {
            'id': 3,
            'file_path': '/test/image3.jpg',
            'file_size': 800,
            'width': 700,
            'height': 500
        }
        
        group.add_image(image1)
        group.add_image(image2)
        group.add_image(image3)
        
        duplicates = group.get_duplicates()
        
        assert len(duplicates) == 2
        assert image1 in duplicates
        assert image3 in duplicates
        assert image2 not in duplicates  # This is the keeper

    def test_to_dict(self):
        """Test converting group to dictionary."""
        group = DuplicateGroup("hash", 0.95)
        
        image1 = {
            'id': 1,
            'file_path': '/test/image1.jpg',
            'file_size': 1000,
            'width': 800,
            'height': 600
        }
        
        image2 = {
            'id': 2,
            'file_path': '/test/image2.jpg',
            'file_size': 1200,
            'width': 1000,
            'height': 800
        }
        
        group.add_image(image1)
        group.add_image(image2)
        
        group_dict = group.to_dict()
        
        assert group_dict['type'] == "hash"
        assert group_dict['similarity_score'] == 0.95
        assert group_dict['total_images'] == 2
        assert group_dict['keeper'] == image2  # Higher resolution
        assert len(group_dict['duplicates']) == 1
        assert group_dict['duplicates'][0] == image1
        assert group_dict['total_size_saved'] == 1000  # Size of duplicate


class TestDuplicateDetector:
    """Test cases for DuplicateDetector class."""

    def test_duplicate_detector_init(self, memory_db):
        """Test DuplicateDetector initialization."""
        detector = DuplicateDetector(memory_db, similarity_threshold=10)
        
        assert detector.database == memory_db
        assert detector.similarity_threshold == 10

    def test_duplicate_detector_init_default_threshold(self, memory_db):
        """Test DuplicateDetector initialization with default threshold."""
        detector = DuplicateDetector(memory_db)
        
        assert detector.similarity_threshold == 5

    def test_find_duplicates_empty_database(self, memory_db):
        """Test finding duplicates in empty database."""
        detector = DuplicateDetector(memory_db)
        groups = detector.find_duplicates()
        
        assert groups == []

    def test_find_duplicates_no_duplicates(self, memory_db, temp_dir):
        """Test finding duplicates when none exist."""
        from src.metadata_extractor import ImageMetadata
        
        # Add unique images to database
        file1 = temp_dir / "unique1.jpg"
        file2 = temp_dir / "unique2.jpg"
        
        metadata1 = ImageMetadata(file1)
        metadata1.file_size = 1000
        metadata1.file_hash = "unique_hash_1"
        metadata1.width = 800
        metadata1.height = 600
        metadata1.perceptual_hash = "phash1"
        
        metadata2 = ImageMetadata(file2)
        metadata2.file_size = 1200
        metadata2.file_hash = "unique_hash_2"
        metadata2.width = 900
        metadata2.height = 700
        metadata2.perceptual_hash = "phash2"
        
        memory_db.store_image_metadata(file1, metadata1)
        memory_db.store_image_metadata(file2, metadata2)
        
        detector = DuplicateDetector(memory_db)
        groups = detector.find_duplicates()
        
        # Should find no duplicates
        assert len(groups) == 0

    def test_find_duplicates_by_hash(self, memory_db, temp_dir):
        """Test finding duplicates by file hash."""
        from src.metadata_extractor import ImageMetadata
        
        # Add images with same hash to database
        file1 = temp_dir / "dup1.jpg"
        file2 = temp_dir / "dup2.jpg"
        
        metadata1 = ImageMetadata(file1)
        metadata1.file_size = 1000
        metadata1.file_hash = "same_hash"
        metadata1.width = 800
        metadata1.height = 600
        
        metadata2 = ImageMetadata(file2)
        metadata2.file_size = 1200
        metadata2.file_hash = "same_hash"  # Same hash
        metadata2.width = 900
        metadata2.height = 700
        
        memory_db.store_image_metadata(file1, metadata1)
        memory_db.store_image_metadata(file2, metadata2)
        
        detector = DuplicateDetector(memory_db)
        groups = detector.find_duplicates()
        
        # Should find one hash duplicate group
        assert len(groups) >= 1
        hash_groups = [g for g in groups if g.type == "hash"]
        assert len(hash_groups) == 1
        assert len(hash_groups[0].images) == 2

    def test_find_duplicates_by_timestamp(self, memory_db, temp_dir):
        """Test finding duplicates by timestamp."""
        from src.metadata_extractor import ImageMetadata
        from datetime import datetime
        
        # Add images with same timestamp to database
        file1 = temp_dir / "time1.jpg"
        file2 = temp_dir / "time2.jpg"
        
        same_time = datetime(2023, 1, 15, 14, 30, 0)
        
        metadata1 = ImageMetadata(file1)
        metadata1.file_size = 1000
        metadata1.file_hash = "hash1"
        metadata1.width = 800
        metadata1.height = 600
        metadata1.timestamp = same_time
        
        metadata2 = ImageMetadata(file2)
        metadata2.file_size = 1200
        metadata2.file_hash = "hash2"
        metadata2.width = 900
        metadata2.height = 700
        metadata2.timestamp = same_time  # Same timestamp
        
        memory_db.store_image_metadata(file1, metadata1)
        memory_db.store_image_metadata(file2, metadata2)
        
        detector = DuplicateDetector(memory_db)
        groups = detector.find_duplicates()
        
        # Should find one timestamp duplicate group
        assert len(groups) >= 1
        timestamp_groups = [g for g in groups if g.type == "timestamp"]
        assert len(timestamp_groups) == 1
        assert len(timestamp_groups[0].images) == 2

    @pytest.mark.slow
    def test_find_duplicates_performance(self, memory_db, temp_dir):
        """Test duplicate detection performance with many images."""
        from src.metadata_extractor import ImageMetadata
        
        # Add many images to database
        for i in range(100):
            file_path = temp_dir / f"image_{i:03d}.jpg"
            metadata = ImageMetadata(file_path)
            metadata.file_size = 1000 + i
            metadata.file_hash = f"hash_{i:03d}"
            metadata.width = 800 + (i % 10)
            metadata.height = 600 + (i % 10)
            metadata.perceptual_hash = f"phash_{i:03d}"
            
            memory_db.store_image_metadata(file_path, metadata)
        
        # Add some actual duplicates
        dup_file1 = temp_dir / "dup1.jpg"
        dup_file2 = temp_dir / "dup2.jpg"
        
        dup_metadata1 = ImageMetadata(dup_file1)
        dup_metadata1.file_size = 2000
        dup_metadata1.file_hash = "duplicate_hash"
        dup_metadata1.width = 1000
        dup_metadata1.height = 800
        
        dup_metadata2 = ImageMetadata(dup_file2)
        dup_metadata2.file_size = 2100
        dup_metadata2.file_hash = "duplicate_hash"  # Same hash
        dup_metadata2.width = 1000
        dup_metadata2.height = 800
        
        memory_db.store_image_metadata(dup_file1, dup_metadata1)
        memory_db.store_image_metadata(dup_file2, dup_metadata2)
        
        detector = DuplicateDetector(memory_db)
        groups = detector.find_duplicates()
        
        # Should find the duplicate group
        assert len(groups) >= 1
        hash_groups = [g for g in groups if g.type == "hash"]
        assert len(hash_groups) >= 1

    def test_duplicate_detector_with_database_groups(self, memory_db, temp_dir):
        """Test that detector creates database groups."""
        from src.metadata_extractor import ImageMetadata
        
        # Add duplicate images
        file1 = temp_dir / "dup1.jpg"
        file2 = temp_dir / "dup2.jpg"
        
        metadata1 = ImageMetadata(file1)
        metadata1.file_size = 1000
        metadata1.file_hash = "same_hash"
        metadata1.width = 800
        metadata1.height = 600
        
        metadata2 = ImageMetadata(file2)
        metadata2.file_size = 1200
        metadata2.file_hash = "same_hash"
        metadata2.width = 900
        metadata2.height = 700
        
        memory_db.store_image_metadata(file1, metadata1)
        memory_db.store_image_metadata(file2, metadata2)
        
        detector = DuplicateDetector(memory_db)
        groups = detector.find_duplicates()
        
        # Verify groups were created
        assert len(groups) >= 1
        
        # Check database groups were created
        db_groups = memory_db.get_duplicate_groups()
        assert len(db_groups) >= 1
