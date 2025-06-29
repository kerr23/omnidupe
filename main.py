#!/usr/bin/env python3
"""
OmniDupe - Duplicate Image Finder
Main entry point for the application.
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from src.image_scanner import ImageScanner
from src.metadata_extractor import MetadataExtractor
from src.duplicate_detector import DuplicateDetector
from src.database import Database
from src.reporter import Reporter
from src.file_manager import FileManager


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the application."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Find and manage duplicate images based on metadata, content, and visual similarity',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --input-dir /path/to/images --output-dir /path/to/results
  %(prog)s -i /photos -o /results --remove-duplicates --dry-run
  %(prog)s -i /photos -o /results --similarity-threshold 5 --verbose
        """
    )
    
    parser.add_argument(
        '--input-dir', '-i',
        type=str,
        default=os.environ.get('INPUT_DIR'),
        help='Directory to scan for images (can also use INPUT_DIR env var)'
    )
    
    parser.add_argument(
        '--output-dir', '-o',
        type=str,
        default=os.environ.get('OUTPUT_DIR', './output'),
        help='Directory to store reports and database (default: ./output, can also use OUTPUT_DIR env var)'
    )
    
    parser.add_argument(
        '--remove-duplicates',
        action='store_true',
        help='Remove duplicate files after generating report (requires confirmation)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without actually deleting files'
    )
    
    parser.add_argument(
        '--similarity-threshold',
        type=int,
        default=10,
        help='Hamming distance threshold for perceptual similarity (default: 10)'
    )
    
    parser.add_argument(
        '--report-format',
        choices=['text', 'csv', 'json'],
        default='text',
        help='Output report format (default: text)'
    )
    
    parser.add_argument(
        '--persistent-db',
        action='store_true',
        help='Keep database file for future runs'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    parser.add_argument(
        '--max-workers',
        type=int,
        default=4,
        help='Maximum number of worker threads for parallel processing (default: 4)'
    )
    
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    """Validate command line arguments."""
    if not args.input_dir:
        print("Error: Input directory must be specified via --input-dir or INPUT_DIR environment variable")
        sys.exit(1)
    
    input_path = Path(args.input_dir)
    if not input_path.exists():
        print(f"Error: Input directory does not exist: {args.input_dir}")
        sys.exit(1)
    
    if not input_path.is_dir():
        print(f"Error: Input path is not a directory: {args.input_dir}")
        sys.exit(1)
    
    # Create output directory if it doesn't exist
    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    if args.similarity_threshold < 0 or args.similarity_threshold > 64:
        print("Error: Similarity threshold must be between 0 and 64")
        sys.exit(1)
    
    if args.max_workers < 1:
        print("Error: Max workers must be at least 1")
        sys.exit(1)


def main() -> int:
    """Main application entry point."""
    args = parse_args()
    validate_args(args)
    setup_logging(args.verbose)
    
    logger = logging.getLogger(__name__)
    logger.info("Starting OmniDupe - Duplicate Image Finder")
    
    try:
        # Initialize components
        db_path = None if not args.persistent_db else Path(args.output_dir) / "omnidupe.db"
        database = Database(db_path)
        
        scanner = ImageScanner(max_workers=args.max_workers)
        metadata_extractor = MetadataExtractor()
        duplicate_detector = DuplicateDetector(
            database=database,
            similarity_threshold=args.similarity_threshold
        )
        reporter = Reporter(output_dir=Path(args.output_dir))
        file_manager = FileManager(dry_run=args.dry_run)
        
        # Step 1: Scan for images
        logger.info(f"Scanning directory: {args.input_dir}")
        image_files = scanner.scan_directory(Path(args.input_dir))
        logger.info(f"Found {len(image_files)} image files")
        
        if not image_files:
            logger.warning("No image files found in the specified directory")
            return 0
        
        # Step 2: Extract metadata and store in database
        logger.info("Extracting metadata from images...")
        for image_path in image_files:
            try:
                metadata = metadata_extractor.extract_metadata(image_path)
                database.store_image_metadata(image_path, metadata)
            except Exception as e:
                logger.warning(f"Failed to process {image_path}: {e}")
        
        # Step 3: Detect duplicates and similar images
        logger.info("Detecting duplicates and similar images...")
        duplicate_groups = duplicate_detector.find_duplicates()
        
        if not duplicate_groups:
            logger.info("No duplicates or similar images found")
            return 0
        
        logger.info(f"Found {len(duplicate_groups)} groups of duplicate/similar images")
        
        # Step 4: Generate report
        logger.info("Generating report...")
        report_path = reporter.generate_report(duplicate_groups, args.report_format)
        logger.info(f"Report saved to: {report_path}")
        
        # Step 5: Optionally remove duplicates
        if args.remove_duplicates:
            if not args.dry_run:
                confirm = input("\nDo you want to proceed with removing duplicate files? (y/N): ")
                if confirm.lower() != 'y':
                    logger.info("Duplicate removal cancelled by user")
                    return 0
            
            logger.info("Processing duplicate removal...")
            removed_count = file_manager.remove_duplicates(duplicate_groups)
            logger.info(f"Removed {removed_count} duplicate files")
        
        logger.info("OmniDupe completed successfully")
        return 0
        
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if args.verbose:
            logger.exception("Full traceback:")
        return 1
    finally:
        # Cleanup
        if 'database' in locals():
            database.close()


if __name__ == "__main__":
    sys.exit(main())
