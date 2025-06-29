"""
Tests for the ImageScanner module.
"""

import pytest
from pathlib import Path

from src.image_scanner import ImageScanner


class TestImageScanner:
    """Test cases for ImageScanner class."""

    def test_scanner_init(self):
        """Test ImageScanner initialization."""
        scanner = ImageScanner(max_workers=2)
        assert scanner.max_workers == 2

    def test_scanner_init_default(self):
        """Test ImageScanner initialization with default workers."""
        scanner = ImageScanner()
        assert scanner.max_workers == 4

    def test_supported_extensions(self):
        """Test getting supported extensions."""
        scanner = ImageScanner()
        extensions = scanner.get_supported_extensions()
        
        assert '.jpg' in extensions
        assert '.jpeg' in extensions
        assert '.png' in extensions
        assert '.gif' in extensions
        assert '.bmp' in extensions
        assert '.webp' in extensions

    def test_supported_mime_types(self):
        """Test getting supported MIME types."""
        scanner = ImageScanner()
        mime_types = scanner.get_supported_mime_types()
        
        assert 'image/jpeg' in mime_types
        assert 'image/png' in mime_types
        assert 'image/gif' in mime_types
        assert 'image/bmp' in mime_types

    def test_is_image_file_by_extension(self, scanner, temp_dir):
        """Test image file detection by extension."""
        # Test valid image files
        jpg_file = temp_dir / "test.jpg"
        png_file = temp_dir / "test.png"
        gif_file = temp_dir / "test.gif"
        
        assert scanner._is_image_file(jpg_file) is True
        assert scanner._is_image_file(png_file) is True
        assert scanner._is_image_file(gif_file) is True
        
        # Test non-image files
        txt_file = temp_dir / "test.txt"
        doc_file = temp_dir / "test.doc"
        
        assert scanner._is_image_file(txt_file) is False
        assert scanner._is_image_file(doc_file) is False

    def test_should_skip_directory(self, scanner, temp_dir):
        """Test directory skipping logic."""
        # Test @eaDir directory (should be skipped)
        eadir = temp_dir / "@eaDir"
        eadir.mkdir()
        assert scanner._should_skip_directory(eadir) is True
        
        # Test case insensitive
        eadir_upper = temp_dir / "@EADIR"
        eadir_upper.mkdir()
        assert scanner._should_skip_directory(eadir_upper) is True
        
        # Test normal directory (should not be skipped)
        normal_dir = temp_dir / "photos"
        normal_dir.mkdir()
        assert scanner._should_skip_directory(normal_dir) is False

    def test_scan_directory_basic(self, scanner, test_images_dir):
        """Test basic directory scanning."""
        image_files = scanner.scan_directory(test_images_dir)
        
        # Should find image files but not skip directories
        assert len(image_files) >= 5  # At least the images we created
        
        # Check that we found expected files
        file_names = [f.name for f in image_files]
        assert 'image1.jpg' in file_names
        assert 'image2.jpg' in file_names
        assert 'image3.png' in file_names
        assert 'duplicate.jpg' in file_names
        assert 'sub_image1.jpg' in file_names
        assert 'sub_image2.png' in file_names
        
        # Should NOT find files in @eaDir
        assert 'should_skip.jpg' not in file_names

    def test_scan_directory_nonexistent(self, scanner, temp_dir):
        """Test scanning non-existent directory."""
        nonexistent = temp_dir / "nonexistent"
        
        with pytest.raises(ValueError, match="Directory does not exist"):
            scanner.scan_directory(nonexistent)

    def test_scan_directory_file_not_directory(self, scanner, temp_dir):
        """Test scanning a file instead of directory."""
        test_file = temp_dir / "test.txt"
        test_file.touch()
        
        with pytest.raises(ValueError, match="Path is not a directory"):
            scanner.scan_directory(test_file)

    def test_scan_directory_empty(self, scanner, temp_dir):
        """Test scanning empty directory."""
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()
        
        image_files = scanner.scan_directory(empty_dir)
        assert len(image_files) == 0

    def test_scan_files_in_directory(self, scanner, test_images_dir):
        """Test scanning files in single directory (non-recursive)."""
        image_files = scanner._scan_files_in_directory(test_images_dir)
        
        # Should only find files in the root directory
        file_names = [f.name for f in image_files]
        assert 'image1.jpg' in file_names
        assert 'image2.jpg' in file_names
        assert 'image3.png' in file_names
        assert 'duplicate.jpg' in file_names
        
        # Should NOT find files in subdirectory
        assert 'sub_image1.jpg' not in file_names
        assert 'sub_image2.png' not in file_names

    def test_scan_files_in_directory_nonexistent(self, scanner, temp_dir):
        """Test scanning files in non-existent directory."""
        nonexistent = temp_dir / "nonexistent"
        
        image_files = scanner._scan_files_in_directory(nonexistent)
        assert len(image_files) == 0

    def test_scan_directory_with_symlinks(self, scanner, temp_dir):
        """Test scanning directory with symbolic links."""
        # Create a real image file
        real_image = temp_dir / "real.jpg"
        create_test_image(real_image, (100, 100), "RGB")
        
        # Create a symbolic link to the image
        link_image = temp_dir / "link.jpg"
        try:
            link_image.symlink_to(real_image)
            
            image_files = scanner.scan_directory(temp_dir)
            
            # Should find the real file but not the symlink
            file_names = [f.name for f in image_files]
            assert 'real.jpg' in file_names
            # Symlinks should be skipped
            assert len([f for f in image_files if f.name == 'link.jpg']) == 0
            
        except OSError:
            # Skip test if symlinks not supported on this system
            pytest.skip("Symlinks not supported on this system")

    def test_scan_directory_permission_error(self, scanner, temp_dir, monkeypatch):
        """Test handling permission errors during scanning."""
        import os
        
        def mock_iterdir(self):
            raise PermissionError("Permission denied")
        
        # Create directory that will raise permission error
        restricted_dir = temp_dir / "restricted"
        restricted_dir.mkdir()
        
        # Mock iterdir to raise PermissionError
        monkeypatch.setattr(Path, "iterdir", mock_iterdir)
        
        # Should handle the error gracefully
        image_files = scanner.scan_directory(temp_dir)
        assert isinstance(image_files, list)  # Should not crash

    def test_scan_directory_single_threaded(self, test_images_dir):
        """Test scanning with single thread."""
        scanner = ImageScanner(max_workers=1)
        image_files = scanner.scan_directory(test_images_dir)
        
        # Should still find all images
        assert len(image_files) >= 5
        file_names = [f.name for f in image_files]
        assert 'image1.jpg' in file_names
        assert 'sub_image1.jpg' in file_names

    def test_scan_directory_multi_threaded(self, test_images_dir):
        """Test scanning with multiple threads."""
        scanner = ImageScanner(max_workers=4)
        image_files = scanner.scan_directory(test_images_dir)
        
        # Should find all images with multiple threads
        assert len(image_files) >= 5
        file_names = [f.name for f in image_files]
        assert 'image1.jpg' in file_names
        assert 'sub_image1.jpg' in file_names

    def test_scan_directory_results_sorted(self, scanner, test_images_dir):
        """Test that scan results are sorted."""
        image_files = scanner.scan_directory(test_images_dir)
        
        # Results should be sorted
        file_paths = [str(f) for f in image_files]
        assert file_paths == sorted(file_paths)

    def test_scan_directory_unique_results(self, scanner, test_images_dir):
        """Test that scan results contain unique files."""
        image_files = scanner.scan_directory(test_images_dir)
        
        # Should have unique results
        file_paths = [str(f) for f in image_files]
        assert len(file_paths) == len(set(file_paths))


def create_test_image(path: Path, size: tuple, mode: str) -> None:
    """Create a test image file."""
    from PIL import Image
    color = (255, 0, 0) if mode == "RGB" else (255, 0, 0, 255)
    image = Image.new(mode, size, color)
    image.save(path)
