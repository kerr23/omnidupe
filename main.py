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
  # Detect duplicates and store in database
  %(prog)s detect --input-dir /path/to/images --output-dir /path/to/results
  
  # Remove images marked for deletion in database
  %(prog)s remove --output-dir /path/to/results
  
  # Protect an image from deletion
  %(prog)s protect --output-dir /path/to/results --file-path /path/to/image.jpg
  
  # Advanced detection with custom threshold
  %(prog)s detect -i /photos -o /results --similarity-threshold 25 --verbose
        """
    )
    
    # Add subcommands
    subparsers = parser.add_subparsers(dest='mode', help='Operation mode', required=True)
    
    # Detect mode
    detect_parser = subparsers.add_parser('detect', help='Detect duplicates and store results')
    detect_parser.add_argument(
        '--input-dir', '-i',
        type=str,
        default=os.environ.get('INPUT_DIR'),
        required=True,
        help='Directory to scan for images'
    )
    detect_parser.add_argument(
        '--output-dir', '-o',
        type=str,
        default=os.environ.get('OUTPUT_DIR', './output'),
        help='Directory to store reports and database (default: ./output)'
    )
    detect_parser.add_argument(
        '--similarity-threshold',
        type=int,
        default=5,
        help='Hamming distance threshold for perceptual similarity (default: 5)'
    )
    detect_parser.add_argument(
        '--report-format',
        choices=['text', 'csv', 'json'],
        default='text',
        help='Output report format (default: text)'
    )
    detect_parser.add_argument(
        '--max-workers',
        type=int,
        default=4,
        help='Maximum number of worker threads (default: 4)'
    )
    detect_parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    # Remove mode  
    remove_parser = subparsers.add_parser('remove', help='Remove or move images marked for deletion')
    remove_parser.add_argument(
        '--output-dir', '-o',
        type=str,
        default=os.environ.get('OUTPUT_DIR', './output'),
        help='Directory containing the database (default: ./output)'
    )
    remove_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without actually deleting files'
    )
    remove_parser.add_argument(
        '--move-to',
        type=str,
        help='Move files to this directory instead of deleting them'
    )
    remove_parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Skip confirmation prompt and proceed automatically'
    )
    remove_parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    # Protect mode
    protect_parser = subparsers.add_parser('protect', help='Mark an image as protected from deletion')
    protect_parser.add_argument(
        '--output-dir', '-o',
        type=str,
        default=os.environ.get('OUTPUT_DIR', './output'),
        help='Directory containing the database (default: ./output)'
    )
    protect_parser.add_argument(
        '--file-path',
        type=str,
        required=True,
        help='Path to image file to protect'
    )
    protect_parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    """Validate command line arguments."""
    # Create output directory if it doesn't exist
    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    if args.mode == 'detect':
        if not args.input_dir:
            print("Error: Input directory must be specified via --input-dir for detect mode")
            sys.exit(1)
        
        input_path = Path(args.input_dir)
        if not input_path.exists():
            print(f"Error: Input directory does not exist: {args.input_dir}")
            sys.exit(1)
        
        if not input_path.is_dir():
            print(f"Error: Input path is not a directory: {args.input_dir}")
            sys.exit(1)
        
        if args.similarity_threshold < 0 or args.similarity_threshold > 64:
            print("Error: Similarity threshold must be between 0 and 64")
            sys.exit(1)
        
        if args.max_workers < 1:
            print("Error: Max workers must be at least 1")
            sys.exit(1)
    
    elif args.mode == 'protect':
        if not args.file_path:
            print("Error: File path must be specified for protect mode")
            sys.exit(1)
        
        file_path = Path(args.file_path)
        if not file_path.exists():
            print(f"Error: File does not exist: {args.file_path}")
            sys.exit(1)
        
        if not file_path.is_file():
            print(f"Error: Path is not a file: {args.file_path}")
            sys.exit(1)


def main() -> int:
    """Main application entry point."""
    args = parse_args()
    validate_args(args)
    setup_logging(args.verbose)
    
    logger = logging.getLogger(__name__)
    logger.info("Starting OmniDupe - Duplicate Image Finder")
    
    database = None
    
    try:
        # Initialize database (always persistent now)
        db_path = Path(args.output_dir) / "omnidupe.db"
        database = Database(db_path)
        
        if args.mode == 'detect':
            return detect_mode(args, database, logger)
        elif args.mode == 'remove':
            return remove_mode(args, database, logger)
        elif args.mode == 'protect':
            return protect_mode(args, database, logger)
        else:
            logger.error(f"Unknown mode: {args.mode}")
            return 1
        
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
        if database:
            database.close()


def detect_mode(args: argparse.Namespace, database: Database, logger) -> int:
    """Handle detect mode - scan for duplicates and store results in database."""
    try:
        # Initialize components
        scanner = ImageScanner(max_workers=args.max_workers)
        metadata_extractor = MetadataExtractor()
        duplicate_detector = DuplicateDetector(
            database=database,
            similarity_threshold=args.similarity_threshold
        )
        reporter = Reporter(output_dir=Path(args.output_dir))
        
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
        
        # Step 4: Convert to database format and mark for removal
        group_dicts = [group.to_dict() for group in duplicate_groups]
        marked_count = database.process_duplicate_groups_for_removal(group_dicts)
        logger.info(f"Marked {marked_count} images for removal")
        
        # Step 5: Generate report
        logger.info("Generating report...")
        report_path = reporter.generate_report(duplicate_groups, args.report_format)
        logger.info(f"Report saved to: {report_path}")
        
        logger.info("Detect mode completed successfully")
        logger.info("Use 'omnidupe remove' to delete the marked duplicate files")
        return 0
        
    except Exception as e:
        logger.error(f"Error in detect mode: {e}")
        raise


def remove_mode(args: argparse.Namespace, database: Database, logger) -> int:
    """Handle remove mode - remove images marked for deletion in database."""
    try:
        # Validate move directory if specified
        move_to_dir = None
        if args.move_to:
            move_to_dir = Path(args.move_to)
            if not args.dry_run:
                move_to_dir.mkdir(parents=True, exist_ok=True)
                if not move_to_dir.is_dir():
                    logger.error(f"Move directory is not valid: {move_to_dir}")
                    return 1
        
        file_manager = FileManager(dry_run=args.dry_run, move_to_dir=move_to_dir)
        
        # Get images marked for removal
        images_to_remove = database.get_images_for_removal()
        
        if not images_to_remove:
            logger.info("No images marked for removal in database")
            logger.info("Run 'omnidupe detect' first to identify duplicates")
            return 0
        
        logger.info(f"Found {len(images_to_remove)} images marked for removal")
        
        # Confirm operation unless dry run
        if not args.dry_run:
            total_size = sum(img.get('file_size', 0) for img in images_to_remove)
            size_mb = total_size / (1024 * 1024)
            
            action = "moved" if args.move_to else "removed"
            action_ing = "moving" if args.move_to else "removing"
            
            print(f"\nFound {len(images_to_remove)} images marked for {action_ing}")
            if args.move_to:
                print(f"Files will be moved to: {args.move_to}")
            print(f"Total size to be processed: {size_mb:.1f} MB")
            print(f"\nFiles to be {action}:")
            for img in images_to_remove[:5]:  # Show first 5
                print(f"  - {img['file_path']} ({img.get('removal_reason', 'unknown')})")
            if len(images_to_remove) > 5:
                print(f"  ... and {len(images_to_remove) - 5} more files")
            
            # Skip confirmation if --yes flag is used or if not in interactive environment
            if args.yes:
                logger.info(f"Auto-confirming {action_ing} due to --yes flag")
            elif not sys.stdin.isatty():
                logger.error("Cannot prompt for confirmation in non-interactive environment")
                logger.error("Use --yes flag to proceed automatically or run with -it flags for Docker")
                return 1
            else:
                try:
                    verb = "move" if args.move_to else "remove"
                    confirm = input(f"\nDo you want to proceed with {action_ing} these files? (y/N): ")
                    if confirm.lower() != 'y':
                        logger.info(f"File {action_ing} cancelled by user")
                        return 0
                except EOFError:
                    logger.error("EOF when reading confirmation - use --yes flag for non-interactive use")
                    return 1
                except KeyboardInterrupt:
                    logger.info(f"File {action_ing} cancelled by user (Ctrl+C)")
                    return 0
        
        # Process files (remove or move)
        processed_count = file_manager.remove_files_from_database(database, args.dry_run)
        
        if args.dry_run:
            action = "moved" if args.move_to else "removed"
            logger.info(f"DRY RUN: Would {action.rstrip('d')} {processed_count} files")
        else:
            action = "moved" if args.move_to else "removed"
            logger.info(f"Successfully {action} {processed_count} files")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error in remove mode: {e}")
        raise


def protect_mode(args: argparse.Namespace, database: Database, logger) -> int:
    """Handle protect mode - mark an image as protected from deletion."""
    try:
        file_path = str(Path(args.file_path).resolve())
        
        success = database.mark_image_protected(file_path)
        
        if success:
            logger.info(f"Successfully protected image: {file_path}")
            logger.info("This image will not be deleted in future removal operations")
            return 0
        else:
            logger.error(f"Failed to protect image: {file_path}")
            logger.error("Image may not exist in the database - run 'omnidupe detect' first")
            return 1
        
    except Exception as e:
        logger.error(f"Error in protect mode: {e}")
        raise


if __name__ == "__main__":
    sys.exit(main())
