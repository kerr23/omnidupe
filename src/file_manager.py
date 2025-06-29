"""
File management module for safe duplicate removal.
"""

import logging
import os
from pathlib import Path
from typing import List, Dict, Any

from .duplicate_detector import DuplicateGroup


class FileManager:
    """Manages file operations for duplicate removal."""
    
    def __init__(self, dry_run: bool = False):
        """
        Initialize file manager.
        
        Args:
            dry_run: If True, only simulate file operations without actual deletion
        """
        self.dry_run = dry_run
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
        Safely remove a single file.
        
        Args:
            file_path: Path to the file to remove
            
        Returns:
            True if file was removed successfully (or would be in dry run mode)
        """
        try:
            if not file_path.exists():
                self.logger.warning(f"File does not exist: {file_path}")
                return False
            
            if not file_path.is_file():
                self.logger.warning(f"Path is not a file: {file_path}")
                return False
            
            # Check file permissions
            if not os.access(file_path, os.W_OK):
                self.logger.warning(f"No write permission for file: {file_path}")
                return False
            
            if self.dry_run:
                self.logger.info(f"DRY RUN: Would remove {file_path}")
                return True
            else:
                # Perform actual deletion
                file_path.unlink()
                return True
                
        except PermissionError:
            self.logger.error(f"Permission denied when removing {file_path}")
            return False
        except OSError as e:
            self.logger.error(f"OS error when removing {file_path}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error when removing {file_path}: {e}")
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
