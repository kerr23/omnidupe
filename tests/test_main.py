"""
Tests for the main application module.
"""

import pytest
import argparse
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys

from main import parse_args, validate_args, detect_mode, remove_mode, protect_mode


class TestArgumentParsing:
    """Test cases for argument parsing."""

    def test_parse_args_detect_mode(self):
        """Test parsing detect mode arguments."""
        test_args = [
            'detect',
            '--input-dir', '/test/input',
            '--output-dir', '/test/output',
            '--similarity-threshold', '10',
            '--report-format', 'csv',
            '--max-workers', '8',
            '--verbose'
        ]
        
        with patch.object(sys, 'argv', ['main.py'] + test_args):
            args = parse_args()
            
            assert args.mode == 'detect'
            assert args.input_dir == '/test/input'
            assert args.output_dir == '/test/output'
            assert args.similarity_threshold == 10
            assert args.report_format == 'csv'
            assert args.max_workers == 8
            assert args.verbose is True

    def test_parse_args_remove_mode(self):
        """Test parsing remove mode arguments."""
        test_args = [
            'remove',
            '--output-dir', '/test/output',
            '--dry-run',
            '--verbose'
        ]
        
        with patch.object(sys, 'argv', ['main.py'] + test_args):
            args = parse_args()
            
            assert args.mode == 'remove'
            assert args.output_dir == '/test/output'
            assert args.dry_run is True
            assert args.verbose is True

    def test_parse_args_protect_mode(self):
        """Test parsing protect mode arguments."""
        test_args = [
            'protect',
            '--output-dir', '/test/output',
            '--file-path', '/test/image.jpg',
            '--verbose'
        ]
        
        with patch.object(sys, 'argv', ['main.py'] + test_args):
            args = parse_args()
            
            assert args.mode == 'protect'
            assert args.output_dir == '/test/output'
            assert args.file_path == '/test/image.jpg'
            assert args.verbose is True

    def test_parse_args_detect_required_input_dir(self):
        """Test that detect mode requires input directory."""
        test_args = ['detect', '--output-dir', '/test/output']
        
        with patch.object(sys, 'argv', ['main.py'] + test_args):
            with pytest.raises(SystemExit):
                parse_args()

    def test_parse_args_protect_required_file_path(self):
        """Test that protect mode requires file path."""
        test_args = ['protect', '--output-dir', '/test/output']
        
        with patch.object(sys, 'argv', ['main.py'] + test_args):
            with pytest.raises(SystemExit):
                parse_args()


class TestArgumentValidation:
    """Test cases for argument validation."""

    def test_validate_args_detect_mode_valid(self, temp_dir):
        """Test validation of valid detect mode arguments."""
        input_dir = temp_dir / "input"
        input_dir.mkdir()
        output_dir = temp_dir / "output"
        
        args = argparse.Namespace(
            mode='detect',
            input_dir=str(input_dir),
            output_dir=str(output_dir),
            similarity_threshold=5,
            max_workers=4
        )
        
        # Should not raise any exception
        validate_args(args)
        
        # Output directory should be created
        assert output_dir.exists()

    def test_validate_args_detect_mode_nonexistent_input(self, temp_dir):
        """Test validation with non-existent input directory."""
        nonexistent_input = temp_dir / "nonexistent"
        output_dir = temp_dir / "output"
        
        args = argparse.Namespace(
            mode='detect',
            input_dir=str(nonexistent_input),
            output_dir=str(output_dir),
            similarity_threshold=5,
            max_workers=4
        )
        
        with pytest.raises(SystemExit):
            validate_args(args)

    def test_validate_args_detect_mode_invalid_threshold(self, temp_dir):
        """Test validation with invalid similarity threshold."""
        input_dir = temp_dir / "input"
        input_dir.mkdir()
        output_dir = temp_dir / "output"
        
        args = argparse.Namespace(
            mode='detect',
            input_dir=str(input_dir),
            output_dir=str(output_dir),
            similarity_threshold=100,  # Invalid (> 64)
            max_workers=4
        )
        
        with pytest.raises(SystemExit):
            validate_args(args)

    def test_validate_args_protect_mode_valid(self, temp_dir):
        """Test validation of valid protect mode arguments."""
        test_file = temp_dir / "test.jpg"
        test_file.touch()
        output_dir = temp_dir / "output"
        
        args = argparse.Namespace(
            mode='protect',
            file_path=str(test_file),
            output_dir=str(output_dir)
        )
        
        # Should not raise any exception
        validate_args(args)

    def test_validate_args_protect_mode_nonexistent_file(self, temp_dir):
        """Test validation with non-existent file."""
        nonexistent_file = temp_dir / "nonexistent.jpg"
        output_dir = temp_dir / "output"
        
        args = argparse.Namespace(
            mode='protect',
            file_path=str(nonexistent_file),
            output_dir=str(output_dir)
        )
        
        with pytest.raises(SystemExit):
            validate_args(args)

    def test_validate_args_remove_mode(self, temp_dir):
        """Test validation of remove mode arguments."""
        output_dir = temp_dir / "output"
        
        args = argparse.Namespace(
            mode='remove',
            output_dir=str(output_dir)
        )
        
        # Should not raise any exception
        validate_args(args)


class TestDetectMode:
    """Test cases for detect mode."""

    @patch('main.ImageScanner')
    @patch('main.MetadataExtractor')
    @patch('main.DuplicateDetector')
    @patch('main.Reporter')
    def test_detect_mode_success(self, mock_reporter, mock_detector, mock_extractor, mock_scanner, temp_dir, memory_db):
        """Test successful detect mode execution."""
        # Setup mocks
        mock_scanner_instance = Mock()
        mock_scanner.return_value = mock_scanner_instance
        mock_scanner_instance.scan_directory.return_value = [
            temp_dir / "image1.jpg",
            temp_dir / "image2.jpg"
        ]
        
        mock_extractor_instance = Mock()
        mock_extractor.return_value = mock_extractor_instance
        
        mock_detector_instance = Mock()
        mock_detector.return_value = mock_detector_instance
        mock_detector_instance.find_duplicates.return_value = []
        
        mock_reporter_instance = Mock()
        mock_reporter.return_value = mock_reporter_instance
        mock_reporter_instance.generate_report.return_value = temp_dir / "report.txt"
        
        # Create args
        args = argparse.Namespace(
            input_dir=str(temp_dir),
            output_dir=str(temp_dir),
            max_workers=4,
            similarity_threshold=5,
            report_format='text'
        )
        
        logger = Mock()
        
        result = detect_mode(args, memory_db, logger)
        
        assert result == 0
        mock_scanner_instance.scan_directory.assert_called_once()
        mock_detector_instance.find_duplicates.assert_called_once()
        # Report is only generated if duplicates are found, so we don't assert it here

    @patch('main.ImageScanner')
    def test_detect_mode_no_images_found(self, mock_scanner, temp_dir, memory_db):
        """Test detect mode when no images are found."""
        mock_scanner_instance = Mock()
        mock_scanner.return_value = mock_scanner_instance
        mock_scanner_instance.scan_directory.return_value = []
        
        args = argparse.Namespace(
            input_dir=str(temp_dir),
            output_dir=str(temp_dir),
            max_workers=4,
            similarity_threshold=5,
            report_format='text'
        )
        
        logger = Mock()
        
        result = detect_mode(args, memory_db, logger)
        
        assert result == 0
        logger.warning.assert_called_with("No image files found in the specified directory")

    @patch('main.ImageScanner')
    @patch('main.MetadataExtractor')
    @patch('main.DuplicateDetector')
    def test_detect_mode_no_duplicates_found(self, mock_detector, mock_extractor, mock_scanner, temp_dir, memory_db):
        """Test detect mode when no duplicates are found."""
        # Setup mocks
        mock_scanner_instance = Mock()
        mock_scanner.return_value = mock_scanner_instance
        mock_scanner_instance.scan_directory.return_value = [temp_dir / "image1.jpg"]
        
        mock_extractor_instance = Mock()
        mock_extractor.return_value = mock_extractor_instance
        
        mock_detector_instance = Mock()
        mock_detector.return_value = mock_detector_instance
        mock_detector_instance.find_duplicates.return_value = []
        
        args = argparse.Namespace(
            input_dir=str(temp_dir),
            output_dir=str(temp_dir),
            max_workers=4,
            similarity_threshold=5,
            report_format='text'
        )
        
        logger = Mock()
        
        result = detect_mode(args, memory_db, logger)
        
        assert result == 0
        logger.info.assert_any_call("No duplicates or similar images found")


class TestRemoveMode:
    """Test cases for remove mode."""

    @patch('main.FileManager')
    def test_remove_mode_no_files_marked(self, mock_file_manager, temp_dir, memory_db):
        """Test remove mode when no files are marked for removal."""
        mock_fm_instance = Mock()
        mock_file_manager.return_value = mock_fm_instance
        
        args = argparse.Namespace(
            output_dir=str(temp_dir),
            dry_run=False,
            move_to=None
        )
        
        logger = Mock()
        
        result = remove_mode(args, memory_db, logger)
        
        assert result == 0
        logger.info.assert_any_call("No images marked for removal in database")

    @patch('main.FileManager')
    @patch('builtins.input', return_value='y')
    def test_remove_mode_with_confirmation(self, mock_input, mock_file_manager, temp_dir, memory_db):
        """Test remove mode with user confirmation."""
        from src.metadata_extractor import ImageMetadata
        
        # Add test image to database and mark for removal
        test_file = temp_dir / "test.jpg"
        metadata = ImageMetadata(test_file)
        metadata.file_size = 1000
        metadata.file_hash = "test"
        metadata.width = 800
        metadata.height = 600
        
        image_id = memory_db.store_image_metadata(test_file, metadata)
        memory_db.mark_image_for_removal(image_id, "duplicate")
        
        mock_fm_instance = Mock()
        mock_file_manager.return_value = mock_fm_instance
        mock_fm_instance.remove_files_from_database.return_value = 1
        
        args = argparse.Namespace(
            output_dir=str(temp_dir),
            dry_run=False,
            move_to=None
        )
        
        logger = Mock()
        
        result = remove_mode(args, memory_db, logger)
        
        assert result == 0
        mock_input.assert_called_once()
        mock_fm_instance.remove_files_from_database.assert_called_once()

    @patch('main.FileManager')
    @patch('builtins.input', return_value='n')
    def test_remove_mode_cancelled(self, mock_input, mock_file_manager, temp_dir, memory_db):
        """Test remove mode cancelled by user."""
        from src.metadata_extractor import ImageMetadata
        
        # Add test image to database and mark for removal
        test_file = temp_dir / "test.jpg"
        metadata = ImageMetadata(test_file)
        metadata.file_size = 1000
        metadata.file_hash = "test"
        metadata.width = 800
        metadata.height = 600
        
        image_id = memory_db.store_image_metadata(test_file, metadata)
        memory_db.mark_image_for_removal(image_id, "duplicate")
        
        mock_fm_instance = Mock()
        mock_file_manager.return_value = mock_fm_instance
        
        args = argparse.Namespace(
            output_dir=str(temp_dir),
            dry_run=False,
            move_to=None
        )
        
        logger = Mock()
        
        result = remove_mode(args, memory_db, logger)
        
        assert result == 0
        mock_input.assert_called_once()
        mock_fm_instance.remove_files_from_database.assert_not_called()

    @patch('main.FileManager')
    def test_remove_mode_dry_run(self, mock_file_manager, temp_dir, memory_db):
        """Test remove mode in dry run mode."""
        from src.metadata_extractor import ImageMetadata
        
        # Add test image to database and mark for removal
        test_file = temp_dir / "test.jpg"
        metadata = ImageMetadata(test_file)
        metadata.file_size = 1000
        metadata.file_hash = "test"
        metadata.width = 800
        metadata.height = 600
        
        image_id = memory_db.store_image_metadata(test_file, metadata)
        memory_db.mark_image_for_removal(image_id, "duplicate")
        
        mock_fm_instance = Mock()
        mock_file_manager.return_value = mock_fm_instance
        mock_fm_instance.remove_files_from_database.return_value = 1
        
        args = argparse.Namespace(
            output_dir=str(temp_dir),
            dry_run=True,
            move_to=None
        )
        
        logger = Mock()
        
        result = remove_mode(args, memory_db, logger)
        
        assert result == 0
        # Should not prompt for confirmation in dry run
        mock_fm_instance.remove_files_from_database.assert_called_once()


class TestProtectMode:
    """Test cases for protect mode."""

    def test_protect_mode_success(self, temp_dir, memory_db):
        """Test successful protect mode execution."""
        from src.metadata_extractor import ImageMetadata
        
        # Add test image to database
        test_file = temp_dir / "test.jpg"
        metadata = ImageMetadata(test_file)
        metadata.file_size = 1000
        metadata.file_hash = "test"
        metadata.width = 800
        metadata.height = 600
        
        memory_db.store_image_metadata(test_file, metadata)
        
        args = argparse.Namespace(
            output_dir=str(temp_dir),
            file_path=str(test_file)
        )
        
        logger = Mock()
        
        result = protect_mode(args, memory_db, logger)
        
        assert result == 0
        logger.info.assert_any_call(f"Successfully protected image: {test_file.resolve()}")

    def test_protect_mode_file_not_in_database(self, temp_dir, memory_db):
        """Test protect mode with file not in database."""
        test_file = temp_dir / "test.jpg"
        
        args = argparse.Namespace(
            output_dir=str(temp_dir),
            file_path=str(test_file)
        )
        
        logger = Mock()
        
        result = protect_mode(args, memory_db, logger)
        
        assert result == 1
        logger.error.assert_any_call(f"Failed to protect image: {test_file.resolve()}")


@pytest.fixture
def mock_args():
    """Create mock arguments for testing."""
    return argparse.Namespace(
        mode='detect',
        input_dir='/test/input',
        output_dir='/test/output',
        similarity_threshold=5,
        max_workers=4,
        verbose=False,
        report_format='text'
    )
