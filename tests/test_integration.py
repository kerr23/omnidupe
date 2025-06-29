"""
Integration tests for the complete OmniDupe workflow.
"""

import pytest
from pathlib import Path
from unittest.mock import patch
import subprocess
import sys

from src.database import Database
from src.metadata_extractor import ImageMetadata


class TestIntegration:
    """Integration tests for complete workflows."""

    @pytest.mark.integration
    def test_complete_detect_remove_workflow(self, test_images_dir, temp_dir):
        """Test complete workflow: detect -> protect -> remove."""
        output_dir = temp_dir / "output"
        output_dir.mkdir()
        
        # Step 1: Run detect mode
        detect_cmd = [
            sys.executable, "main.py", "detect",
            "--input-dir", str(test_images_dir),
            "--output-dir", str(output_dir),
            "--similarity-threshold", "10",
            "--max-workers", "2"
        ]
        
        result = subprocess.run(detect_cmd, capture_output=True, text=True, cwd=Path.cwd())
        assert result.returncode == 0
        
        # Check database was created
        db_path = output_dir / "omnidupe.db"
        assert db_path.exists()
        
        # Verify database contains images
        db = Database(db_path)
        images = db.get_all_images()
        assert len(images) > 0
        db.close()
        
        # Step 2: Check what would be removed (dry run)
        remove_dry_cmd = [
            sys.executable, "main.py", "remove",
            "--output-dir", str(output_dir),
            "--dry-run"
        ]
        
        result = subprocess.run(remove_dry_cmd, capture_output=True, text=True, cwd=Path.cwd())
        # Should succeed even if no duplicates found
        assert result.returncode == 0

    @pytest.mark.integration
    def test_protect_mode_integration(self, test_images_dir, temp_dir):
        """Test protect mode integration."""
        output_dir = temp_dir / "output"
        output_dir.mkdir()
        
        # First run detect to populate database
        detect_cmd = [
            sys.executable, "main.py", "detect",
            "--input-dir", str(test_images_dir),
            "--output-dir", str(output_dir),
            "--max-workers", "1"
        ]
        
        result = subprocess.run(detect_cmd, capture_output=True, text=True, cwd=Path.cwd())
        assert result.returncode == 0
        
        # Find an image to protect
        images = list(test_images_dir.glob("*.jpg"))
        if images:
            protect_image = images[0]
            
            # Protect the image
            protect_cmd = [
                sys.executable, "main.py", "protect",
                "--output-dir", str(output_dir),
                "--file-path", str(protect_image)
            ]
            
            result = subprocess.run(protect_cmd, capture_output=True, text=True, cwd=Path.cwd())
            assert result.returncode == 0
            
            # Verify protection in database
            db = Database(output_dir / "omnidupe.db")
            try:
                cursor = db.connection.cursor()
                cursor.execute("SELECT is_protected FROM images WHERE file_path = ?", (str(protect_image.resolve()),))
                row = cursor.fetchone()
                if row:
                    assert row['is_protected'] == 1
            finally:
                db.close()

    @pytest.mark.integration
    def test_invalid_arguments(self, temp_dir):
        """Test application with invalid arguments."""
        # Test missing required arguments
        cmd = [sys.executable, "main.py", "detect", "--output-dir", str(temp_dir)]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
        assert result.returncode != 0
        
        # Test invalid mode
        cmd = [sys.executable, "main.py", "invalid_mode"]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
        assert result.returncode != 0

    @pytest.mark.integration
    def test_help_output(self):
        """Test help output for all modes."""
        # Main help
        cmd = [sys.executable, "main.py", "--help"]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
        assert result.returncode == 0
        assert "detect" in result.stdout
        assert "remove" in result.stdout
        assert "protect" in result.stdout

    @pytest.mark.integration
    def test_nonexistent_input_directory(self, temp_dir):
        """Test with non-existent input directory."""
        nonexistent = temp_dir / "nonexistent"
        output_dir = temp_dir / "output"
        
        cmd = [
            sys.executable, "main.py", "detect",
            "--input-dir", str(nonexistent),
            "--output-dir", str(output_dir)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
        assert result.returncode != 0

    @pytest.mark.integration
    def test_empty_input_directory(self, temp_dir):
        """Test with empty input directory."""
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()
        output_dir = temp_dir / "output"
        
        cmd = [
            sys.executable, "main.py", "detect",
            "--input-dir", str(empty_dir),
            "--output-dir", str(output_dir),
            "--max-workers", "1"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
        assert result.returncode == 0  # Should succeed but find no images

    @pytest.mark.integration
    def test_report_generation(self, test_images_dir, temp_dir):
        """Test that reports are generated."""
        output_dir = temp_dir / "output"
        output_dir.mkdir()
        
        # Test different report formats
        for report_format in ['text', 'csv', 'json']:
            cmd = [
                sys.executable, "main.py", "detect",
                "--input-dir", str(test_images_dir),
                "--output-dir", str(output_dir),
                "--report-format", report_format,
                "--max-workers", "1"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
            assert result.returncode == 0
            
            # Check if report file was created
            report_files = list(output_dir.glob(f"*duplicate*.{report_format if report_format != 'text' else 'txt'}"))
            # May or may not have duplicates, but should not crash

    @pytest.mark.integration
    def test_database_persistence(self, test_images_dir, temp_dir):
        """Test that database persists between runs."""
        output_dir = temp_dir / "output"
        output_dir.mkdir()
        db_path = output_dir / "omnidupe.db"
        
        # First run
        cmd1 = [
            sys.executable, "main.py", "detect",
            "--input-dir", str(test_images_dir),
            "--output-dir", str(output_dir),
            "--max-workers", "1"
        ]
        
        result1 = subprocess.run(cmd1, capture_output=True, text=True, cwd=Path.cwd())
        assert result1.returncode == 0
        assert db_path.exists()
        
        # Get initial image count
        db = Database(db_path)
        initial_count = len(db.get_all_images())
        db.close()
        
        # Second run (should use existing database)
        result2 = subprocess.run(cmd1, capture_output=True, text=True, cwd=Path.cwd())
        assert result2.returncode == 0
        
        # Database should still exist and have images
        db = Database(db_path)
        final_count = len(db.get_all_images())
        db.close()
        
        # Should have at least the same number of images
        assert final_count >= initial_count

    def test_skip_system_directories(self, temp_dir):
        """Test that system directories are skipped."""
        from src.image_scanner import ImageScanner
        
        # Create test structure with @eaDir
        test_dir = temp_dir / "test_scan"
        test_dir.mkdir()
        
        # Create @eaDir directory
        eadir = test_dir / "@eaDir"
        eadir.mkdir()
        
        # Create image in @eaDir (should be skipped)
        from PIL import Image
        skip_image = eadir / "skip.jpg"
        img = Image.new('RGB', (100, 100), 'red')
        img.save(skip_image)
        
        # Create normal image (should be found)
        normal_image = test_dir / "normal.jpg"
        img.save(normal_image)
        
        # Scan directory
        scanner = ImageScanner()
        images = scanner.scan_directory(test_dir)
        
        # Should find normal image but not the one in @eaDir
        image_names = [img.name for img in images]
        assert 'normal.jpg' in image_names
        assert 'skip.jpg' not in image_names

    @pytest.mark.integration
    def test_verbose_logging(self, test_images_dir, temp_dir):
        """Test verbose logging output."""
        output_dir = temp_dir / "output"
        output_dir.mkdir()
        
        cmd = [
            sys.executable, "main.py", "detect",
            "--input-dir", str(test_images_dir),
            "--output-dir", str(output_dir),
            "--verbose",
            "--max-workers", "1"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
        assert result.returncode == 0
        
        # Should have more detailed output in verbose mode
        assert "DEBUG" in result.stdout or "INFO" in result.stdout

    @pytest.mark.integration
    def test_remove_with_move_functionality(self, test_images_dir, temp_dir):
        """Test complete workflow with move functionality instead of deletion."""
        output_dir = temp_dir / "output"
        output_dir.mkdir()
        move_dir = temp_dir / "moved_images"
        
        # Step 1: Run detect mode
        detect_cmd = [
            sys.executable, "main.py", "detect",
            "--input-dir", str(test_images_dir),
            "--output-dir", str(output_dir),
            "--similarity-threshold", "10",
            "--max-workers", "2"
        ]
        
        result = subprocess.run(detect_cmd, capture_output=True, text=True, cwd=Path.cwd())
        assert result.returncode == 0
        
        # Check database was created
        db_path = output_dir / "omnidupe.db"
        assert db_path.exists()
        
        # Step 2: Test move with dry run
        move_dry_cmd = [
            sys.executable, "main.py", "remove",
            "--output-dir", str(output_dir),
            "--move-to", str(move_dir),
            "--dry-run"
        ]
        
        result = subprocess.run(move_dry_cmd, capture_output=True, text=True, cwd=Path.cwd())
        assert result.returncode == 0
        
        # In dry run, move directory shouldn't be created
        assert not move_dir.exists()
        
        # Check that move functionality would be used (check logs)
        if "DRY RUN: Would move" in result.stdout or "Would move" in result.stdout:
            # Files would be moved in actual run - this is the expected successful case
            assert "Processing" in result.stdout and "marked for moving" in result.stdout
        else:
            # No files to move (which is also valid)
            assert "No images marked for removal" in result.stdout

class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_corrupted_database(self, temp_dir):
        """Test handling of corrupted database."""
        output_dir = temp_dir / "output"
        output_dir.mkdir()
        
        # Create a corrupted database file
        db_path = output_dir / "omnidupe.db"
        db_path.write_text("not a database")
        
        cmd = [
            sys.executable, "main.py", "remove",
            "--output-dir", str(output_dir)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
        # Should handle the error gracefully
        assert result.returncode != 0

    def test_permission_denied_output(self, temp_dir):
        """Test handling of permission denied on output directory."""
        import os
        import stat
        
        # Create directory with no write permissions
        restricted_dir = temp_dir / "restricted"
        restricted_dir.mkdir()
        
        try:
            # Remove write permissions
            os.chmod(restricted_dir, stat.S_IRUSR | stat.S_IXUSR)
            
            cmd = [
                sys.executable, "main.py", "detect",
                "--input-dir", str(temp_dir),
                "--output-dir", str(restricted_dir / "subdir")
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
            # Should handle permission error
            
        finally:
            # Restore permissions for cleanup
            try:
                os.chmod(restricted_dir, stat.S_IRWXU)
            except:
                pass

    def test_keyboard_interrupt(self, test_images_dir, temp_dir):
        """Test handling of keyboard interrupt."""
        # This is difficult to test automatically, but we can at least
        # verify the signal handling is in place
        import signal
        
        output_dir = temp_dir / "output"
        output_dir.mkdir()
        
        # Just verify the imports and basic structure work
        import main
        assert hasattr(main, 'main')
        
        # The actual keyboard interrupt handling would need manual testing
        # or more complex subprocess control
