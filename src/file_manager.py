"""
File management module for safe duplicate removal.
"""

import logging
import os
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional

from .duplicate_detector import DuplicateGroup


class FileManager:
    """Manages file operations for duplicate removal."""
    
    def __init__(self, dry_run: bool = False, move_to_dir: Optional[Path] = None):
        """
        Initialize file manager.
        
        Args:
            dry_run: If True, only simulate file operations without actual deletion/moving
            move_to_dir: If provided, move files to this directory instead of deleting them
        """
        self.dry_run = dry_run
        self.move_to_dir = move_to_dir
        self.logger = logging.getLogger(__name__)
    
    def remove_duplicates(self, duplicate_groups: List[DuplicateGroup]) -> int:
        """
        Remove duplicate files, keeping only the selected keeper in each group.
        
        Args:
            duplicate_groups: List of DuplicateGroup objects
            
        Returns:
            Number of files actually removed
        """
        if not duplicate_groups:
            self.logger.info("No duplicate groups to process")
            return 0
        
        removed_count = 0
        total_duplicates = sum(len(group.get_duplicates()) for group in duplicate_groups)
        
        self.logger.info(f"Processing {len(duplicate_groups)} duplicate groups "
                        f"({total_duplicates} files to remove)")
        
        if self.dry_run:
            self.logger.info("DRY RUN MODE - No files will actually be deleted")
        
        for i, group in enumerate(duplicate_groups, 1):
            group_data = group.to_dict()
            duplicates = group_data['duplicates']
            
            self.logger.info(f"Processing group {i}/{len(duplicate_groups)} "
                           f"({len(duplicates)} files to remove)")
            
            for duplicate in duplicates:
                file_path = Path(duplicate['file_path'])
                
                try:
                    if self._remove_file(file_path):
                        removed_count += 1
                        self.logger.debug(f"Removed: {file_path}")
                    else:
                        self.logger.warning(f"Failed to remove: {file_path}")
                        
                except Exception as e:
                    self.logger.error(f"Error removing {file_path}: {e}")
        
        if self.dry_run:
            self.logger.info(f"DRY RUN: Would have removed {removed_count} files")
        else:
            self.logger.info(f"Successfully removed {removed_count} duplicate files")
        
        return removed_count
    
    def _remove_file(self, file_path: Path) -> bool:
        """
        Safely remove or move a single file.
        
        Args:
            file_path: Path to the file to remove or move
            
        Returns:
            True if file was removed/moved successfully (or would be in dry run mode)
        """
        try:
            if not file_path.exists():
                self.logger.warning(f"File does not exist: {file_path}")
                return False
            
            if not file_path.is_file():
                self.logger.warning(f"Path is not a file: {file_path}")
                return False
            
            # Check file permissions
            if not self._check_write_permission(file_path):
                self.logger.warning(f"No write permission for file: {file_path}")
                return False
            
            if self.dry_run:
                if self.move_to_dir:
                    self.logger.info(f"DRY RUN: Would move {file_path} to {self.move_to_dir}")
                else:
                    self.logger.info(f"DRY RUN: Would remove {file_path}")
                return True
            else:
                if self.move_to_dir:
                    # Move file to destination directory
                    return self._move_file_to_directory(file_path, self.move_to_dir)
                else:
                    # Perform actual deletion
                    file_path.unlink()
                    return True
                
        except PermissionError:
            self.logger.error(f"Permission denied when processing {file_path}")
            return False
        except FileNotFoundError:
            self.logger.warning(f"File not found (already removed?): {file_path}")
            return True  # Consider this a success
        except OSError as e:
            self.logger.error(f"OS error when processing {file_path}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error when processing {file_path}: {e}")
            return False
    
    def verify_keeper_files(self, duplicate_groups: List[DuplicateGroup]) -> Dict[str, Any]:
        """
        Verify that all keeper files still exist and are accessible.
        
        Args:
            duplicate_groups: List of DuplicateGroup objects
            
        Returns:
            Dictionary with verification results
        """
        results = {
            'total_keepers': 0,
            'accessible_keepers': 0,
            'missing_keepers': [],
            'inaccessible_keepers': []
        }
        
        for group in duplicate_groups:
            group_data = group.to_dict()
            keeper = group_data['keeper']
            keeper_path = Path(keeper['file_path'])
            
            results['total_keepers'] += 1
            
            if not keeper_path.exists():
                results['missing_keepers'].append(str(keeper_path))
                self.logger.warning(f"Keeper file missing: {keeper_path}")
                continue
            
            if not keeper_path.is_file():
                results['inaccessible_keepers'].append(str(keeper_path))
                self.logger.warning(f"Keeper path is not a file: {keeper_path}")
                continue
            
            if not os.access(keeper_path, os.R_OK):
                results['inaccessible_keepers'].append(str(keeper_path))
                self.logger.warning(f"Keeper file not readable: {keeper_path}")
                continue
            
            results['accessible_keepers'] += 1
        
        success_rate = (results['accessible_keepers'] / results['total_keepers'] * 100 
                       if results['total_keepers'] > 0 else 0)
        
        self.logger.info(f"Keeper verification: {results['accessible_keepers']}/{results['total_keepers']} "
                        f"files accessible ({success_rate:.1f}%)")
        
        return results
    
    def create_backup_script(self, duplicate_groups: List[DuplicateGroup], output_path: Path) -> Path:
        """
        Create a shell script that can be used to remove duplicates manually.
        
        Args:
            duplicate_groups: List of DuplicateGroup objects
            output_path: Path where to save the script
            
        Returns:
            Path to the created script
        """
        script_path = output_path / "remove_duplicates.sh"
        
        try:
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write("#!/bin/bash\n")
                f.write("# OmniDupe - Duplicate Removal Script\n")
                f.write("# Generated automatically - review before execution\n")
                f.write("#\n")
                f.write("# This script will remove duplicate files identified by OmniDupe\n")
                f.write("# IMPORTANT: Review this script carefully before running!\n")
                f.write("#\n\n")
                
                f.write("set -e  # Exit on any error\n\n")
                
                f.write("echo 'OmniDupe Duplicate Removal Script'\n")
                f.write("echo 'WARNING: This will permanently delete files!'\n")
                f.write("echo 'Press Ctrl+C to cancel, or Enter to continue...'\n")
                f.write("read\n\n")
                
                total_files = sum(len(group.get_duplicates()) for group in duplicate_groups)
                f.write(f"echo 'Removing {total_files} duplicate files...'\n\n")
                
                for i, group in enumerate(duplicate_groups, 1):
                    group_data = group.to_dict()
                    f.write(f"# Group {i}: {group.type} duplicates\n")
                    f.write(f"# Keeping: {group_data['keeper']['file_path']}\n")
                    
                    for duplicate in group_data['duplicates']:
                        file_path = duplicate['file_path']
                        # Escape shell special characters
                        escaped_path = file_path.replace("'", "'\"'\"'")
                        f.write(f"rm -f '{escaped_path}'\n")
                    
                    f.write("\n")
                
                f.write("echo 'Duplicate removal completed.'\n")
            
            # Make script executable
            script_path.chmod(0o755)
            
            self.logger.info(f"Backup removal script created: {script_path}")
            return script_path
            
        except Exception as e:
            self.logger.error(f"Error creating backup script: {e}")
            raise
    
    def get_file_info(self, file_path: Path) -> Dict[str, Any]:
        """
        Get detailed information about a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dictionary with file information
        """
        info = {
            'exists': False,
            'is_file': False,
            'size': 0,
            'readable': False,
            'writable': False,
            'error': None
        }
        
        try:
            info['exists'] = file_path.exists()
            
            if info['exists']:
                info['is_file'] = file_path.is_file()
                
                if info['is_file']:
                    stat_info = file_path.stat()
                    info['size'] = stat_info.st_size
                    info['readable'] = os.access(file_path, os.R_OK)
                    info['writable'] = os.access(file_path, os.W_OK)
                    
        except Exception as e:
            info['error'] = str(e)
        
        return info

    def remove_files_from_database(self, database, dry_run: bool = False) -> int:
        """
        Remove or move files that are marked for removal in the database.
        
        Args:
            database: Database instance to query for files to remove
            dry_run: If True, only simulate file operations without actual deletion/moving
            
        Returns:
            Number of files actually processed (removed or moved)
        """
        images_to_remove = database.get_images_for_removal()
        
        if not images_to_remove:
            self.logger.info("No images marked for removal in database")
            return 0
        
        processed_count = 0
        action = "moving" if self.move_to_dir else "removing"
        self.logger.info(f"Processing {len(images_to_remove)} images marked for {action}")
        
        if dry_run:
            self.logger.info(f"DRY RUN MODE - No files will actually be {action.rstrip('ing')}ed")
        
        for image_info in images_to_remove:
            file_path = Path(image_info['file_path'])
            image_id = image_info['id']
            reason = image_info.get('removal_reason', 'unknown')
            
            try:
                if self._remove_file_and_update_db(file_path, image_id, database, dry_run):
                    processed_count += 1
                    action_past = "moved" if self.move_to_dir else "removed"
                    self.logger.debug(f"{action_past.capitalize()} ({reason}): {file_path}")
                else:
                    self.logger.warning(f"Failed to {action.rstrip('ing')} {file_path}")
                    
            except Exception as e:
                self.logger.error(f"Error {action.rstrip('ing')} {file_path}: {e}")
        
        if dry_run:
            action_past = "moved" if self.move_to_dir else "removed"
            self.logger.info(f"DRY RUN: Would have {action_past} {processed_count} files")
        else:
            action_past = "moved" if self.move_to_dir else "removed"
            self.logger.info(f"Successfully {action_past} {processed_count} files")
        
        return processed_count

    def _remove_file_and_update_db(self, file_path: Path, image_id: int, database, dry_run: bool = False) -> bool:
        """
        Remove or move a file and update the database record.
        
        Args:
            file_path: Path to the file to remove or move
            image_id: Database ID of the image
            database: Database instance to update
            dry_run: If True, only simulate the operation
            
        Returns:
            True if file was removed/moved successfully (or would be in dry run mode)
        """
        try:
            if not file_path.exists():
                self.logger.warning(f"File does not exist: {file_path}")
                # File already gone, remove the database record
                if not dry_run:
                    try:
                        database.unmark_image_for_removal(image_id)
                    except Exception as db_error:
                        self.logger.warning(f"Failed to update database for missing file {file_path}: {db_error}")
                return True
            
            if not file_path.is_file():
                self.logger.warning(f"Path is not a file: {file_path}")
                return False
            
            # Check file permissions
            if not os.access(file_path, os.W_OK):
                self.logger.warning(f"No write permission for file: {file_path}")
                return False
            
            if dry_run:
                if self.move_to_dir:
                    self.logger.info(f"DRY RUN: Would move {file_path} to {self.move_to_dir}")
                else:
                    self.logger.info(f"DRY RUN: Would remove {file_path}")
                return True
            else:
                success = False
                if self.move_to_dir:
                    # Move file to destination directory
                    success = self._move_file_to_directory(file_path, self.move_to_dir)
                else:
                    # Perform actual deletion
                    file_path.unlink()
                    success = True
                
                if success:
                    # Update database to unmark the processed file
                    try:
                        database.unmark_image_for_removal(image_id)
                    except Exception as db_error:
                        self.logger.warning(f"Failed to update database for {file_path}: {db_error}")
                        # File operation was successful, so don't fail the entire operation
                        # just because database update failed
                
                return success
                
        except PermissionError:
            self.logger.error(f"Permission denied when processing {file_path}")
            return False
        except OSError as e:
            self.logger.error(f"OS error when processing {file_path}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error when processing {file_path}: {e}")
            return False
    
    def _check_write_permission(self, file_path: Path) -> bool:
        """
        Check if we have write permission for a file or its parent directory.
        
        Args:
            file_path: Path to the file to check
            
        Returns:
            True if we have write permission, False otherwise
        """
        try:
            # Check if file exists and is writable
            if file_path.exists():
                return os.access(file_path, os.W_OK)
            
            # Check if parent directory is writable (for new files)
            parent_dir = file_path.parent
            return parent_dir.exists() and os.access(parent_dir, os.W_OK)
            
        except (OSError, PermissionError):
            return False

    def _move_file_to_directory(self, file_path: Path, dest_dir: Path) -> bool:
        """
        Move a file to a destination directory, preserving directory structure.
        
        Args:
            file_path: Source file path
            dest_dir: Destination directory
            
        Returns:
            True if file was moved successfully
        """
        try:
            # Check source file permissions
            if not self._check_write_permission(file_path):
                self.logger.warning(f"No write permission for source file: {file_path}")
                return False
            
            # Create destination directory if it doesn't exist
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            # Check destination directory permissions
            test_file = dest_dir / ".write_test"
            try:
                if not self.dry_run:
                    test_file.touch()
                    test_file.unlink()
            except (OSError, PermissionError):
                self.logger.warning(f"No write permission for destination directory: {dest_dir}")
                return False
            
            # Generate destination path, handling name conflicts
            dest_file = dest_dir / file_path.name
            original_stem = file_path.stem
            original_suffix = file_path.suffix
            
            # If file already exists, create a unique name using timestamp
            if dest_file.exists():
                import time
                timestamp = int(time.time() * 1000)  # milliseconds for better uniqueness
                counter = 1
                
                # Try with timestamp first
                new_name = f"{original_stem}_{timestamp}{original_suffix}"
                dest_file = dest_dir / new_name
                
                # If still conflicts (very unlikely but possible), add counter
                while dest_file.exists():
                    new_name = f"{original_stem}_{timestamp}_{counter}{original_suffix}"
                    dest_file = dest_dir / new_name
                    counter += 1
                    
                    # Safety check to prevent infinite loop
                    if counter > 1000:
                        raise Exception(f"Cannot generate unique filename for {file_path.name} after 1000 attempts")
            
            if self.dry_run:
                self.logger.info(f"DRY RUN: Would move {file_path} to {dest_file}")
                return True
            
            # Move the file
            shutil.move(str(file_path), str(dest_file))
            self.logger.info(f"Moved {file_path} to {dest_file}")
            return True
            
        except PermissionError as e:
            self.logger.error(f"Permission denied moving {file_path}: {e}")
            return False
        except OSError as e:
            self.logger.error(f"OS error moving {file_path}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error moving {file_path}: {e}")
            return False
