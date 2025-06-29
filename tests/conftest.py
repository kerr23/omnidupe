"""
Pytest configuration and shared fixtures.
"""

import os
import tempfile
import shutil
from pathlib import Path
from typing import Generator
import pytest
from PIL import Image
import sqlite3

from src.database import Database
from src.metadata_extractor import ImageMetadata
from src.image_scanner import ImageScanner
from src.duplicate_detector import DuplicateDetector
from src.file_manager import FileManager


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_db(temp_dir: Path) -> Generator[Database, None, None]:
    """Create a test database."""
    db_path = temp_dir / "test.db"
    db = Database(db_path)
    yield db
    db.close()


@pytest.fixture
def memory_db() -> Generator[Database, None, None]:
    """Create an in-memory test database."""
    db = Database(None)  # In-memory database
    yield db
    db.close()


@pytest.fixture
def sample_image_metadata(temp_dir: Path) -> ImageMetadata:
    """Create sample image metadata for testing."""
    from datetime import datetime
    
    file_path = temp_dir / "sample.jpg"
    metadata = ImageMetadata(file_path)
    metadata.file_size = 1024000
    metadata.file_hash = "abcd1234567890"
    metadata.width = 1920
    metadata.height = 1080
    metadata.format = "JPEG"
    metadata.timestamp = datetime(2023, 1, 15, 14, 30, 0)
    metadata.camera_make = "Canon"
    metadata.camera_model = "EOS R5"
    metadata.perceptual_hash = "0123456789abcdef"
    metadata.average_hash = "fedcba9876543210"
    metadata.difference_hash = "1111222233334444"
    metadata.wavelet_hash = "aaaa1111bbbb2222"
    metadata.creation_time = datetime(2023, 1, 15, 14, 30, 0)
    metadata.modification_time = datetime(2023, 1, 15, 14, 30, 0)
    
    return metadata


@pytest.fixture
def test_images_dir(temp_dir: Path) -> Path:
    """Create a directory with test image files."""
    images_dir = temp_dir / "test_images"
    images_dir.mkdir()
    
    # Create test images
    create_test_image(images_dir / "image1.jpg", (100, 100), "RGB")
    create_test_image(images_dir / "image2.jpg", (200, 200), "RGB")
    create_test_image(images_dir / "image3.png", (150, 150), "RGBA")
    create_test_image(images_dir / "duplicate.jpg", (100, 100), "RGB")  # Same size as image1
    
    # Create subdirectory with more images
    subdir = images_dir / "subdir"
    subdir.mkdir()
    create_test_image(subdir / "sub_image1.jpg", (300, 300), "RGB")
    create_test_image(subdir / "sub_image2.png", (400, 400), "RGBA")
    
    # Create @eaDir directory (should be skipped)
    skip_dir = images_dir / "@eaDir"
    skip_dir.mkdir()
    create_test_image(skip_dir / "should_skip.jpg", (50, 50), "RGB")
    
    return images_dir


def create_test_image(path: Path, size: tuple, mode: str) -> None:
    """Create a test image file."""
    # Create a simple colored image
    color = (255, 0, 0) if mode == "RGB" else (255, 0, 0, 255)
    image = Image.new(mode, size, color)
    image.save(path)


@pytest.fixture
def scanner() -> ImageScanner:
    """Create an ImageScanner instance."""
    return ImageScanner(max_workers=2)


@pytest.fixture
def file_manager() -> FileManager:
    """Create a FileManager instance."""
    return FileManager(dry_run=True)


@pytest.fixture 
def duplicate_detector(test_db: Database) -> DuplicateDetector:
    """Create a DuplicateDetector instance."""
    return DuplicateDetector(database=test_db, similarity_threshold=5)


@pytest.fixture
def populated_db(test_db: Database, sample_image_metadata: ImageMetadata, temp_dir: Path) -> Database:
    """Create a database populated with test data."""
    # Store some test image metadata
    test_paths = [
        temp_dir / "image1.jpg",
        temp_dir / "image2.jpg", 
        temp_dir / "duplicate1.jpg",
        temp_dir / "duplicate2.jpg"
    ]
    
    for i, path in enumerate(test_paths):
        # Create variations of the metadata
        metadata = ImageMetadata(path)
        metadata.file_size = 1024000 + (i * 1000)
        metadata.file_hash = f"hash{i:04d}"
        metadata.width = 1920 + (i * 100)
        metadata.height = 1080 + (i * 100)
        metadata.format = "JPEG"
        metadata.perceptual_hash = f"phash{i:04d}"
        metadata.average_hash = f"ahash{i:04d}"
        
        test_db.store_image_metadata(path, metadata)
    
    return test_db


@pytest.fixture
def mock_file_operations(monkeypatch):
    """Mock file operations to prevent actual file deletion in tests."""
    deleted_files = []
    
    def mock_unlink(self):
        deleted_files.append(str(self))
        
    def mock_exists(self):
        return str(self) not in deleted_files
        
    def mock_is_file(self):
        return str(self) not in deleted_files and not str(self).endswith('/')
        
    monkeypatch.setattr(Path, "unlink", mock_unlink)
    monkeypatch.setattr(Path, "exists", mock_exists)
    monkeypatch.setattr(Path, "is_file", mock_is_file)
    
    return deleted_files
