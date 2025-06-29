"""
Image scanner module for recursive directory traversal and image file detection.
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Set
import mimetypes


class ImageScanner:
    """Scanner for recursively finding image files in directories."""
    
    # Supported image file extensions
    SUPPORTED_EXTENSIONS = {
        '.jpg', '.jpeg', '.png', '.gif', '.tiff', '.tif', 
        '.bmp', '.webp', '.ico', '.jfif', '.pjpeg', '.pjp'
    }
    
    # MIME types for additional validation
    IMAGE_MIME_TYPES = {
        'image/jpeg', 'image/png', 'image/gif', 'image/tiff',
        'image/bmp', 'image/webp', 'image/x-icon', 'image/vnd.microsoft.icon'
    }
    
    # Directories to skip during scanning
    SKIP_DIRECTORIES = {
        '@eaDir',  # Synology NAS system directory
    }
    
    def __init__(self, max_workers: int = 4):
        """
        Initialize the image scanner.
        
        Args:
            max_workers: Maximum number of threads for parallel processing
        """
        self.max_workers = max_workers
        self.logger = logging.getLogger(__name__)
        
        # Initialize mimetypes
        mimetypes.init()
    
    def _should_skip_directory(self, directory: Path) -> bool:
        """
        Check if a directory should be skipped during scanning.
        
        Args:
            directory: Directory to check
            
        Returns:
            True if the directory should be skipped
        """
        directory_name = directory.name
        
        # Check against known directories to skip (case-insensitive)
        for skip_dir in self.SKIP_DIRECTORIES:
            if directory_name.lower() == skip_dir.lower():
                self.logger.debug(f"Skipping directory: {directory}")
                return True
        
        return False
    
    def _is_image_file(self, file_path: Path) -> bool:
        """
        Check if a file is a supported image format.
        
        Args:
            file_path: Path to the file to check
            
        Returns:
            True if the file is a supported image format
        """
        # Check file extension
        if file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
            return True
        
        # Check MIME type as fallback
        try:
            mime_type, _ = mimetypes.guess_type(str(file_path))
            if mime_type and mime_type in self.IMAGE_MIME_TYPES:
                return True
        except Exception:
            pass
        
        return False
    
    def _scan_directory_worker(self, directory: Path) -> List[Path]:
        """
        Worker function to scan a single directory for image files.
        
        Args:
            directory: Directory to scan
            
        Returns:
            List of image file paths found in the directory
        """
        image_files = []
        
        try:
            if not directory.exists() or not directory.is_dir():
                return image_files
            
            for item in directory.iterdir():
                try:
                    if item.is_file() and not item.is_symlink():
                        if self._is_image_file(item):
                            image_files.append(item.resolve())
                    elif item.is_dir() and not item.is_symlink():
                        # Skip directories that should be ignored
                        if self._should_skip_directory(item):
                            continue
                        # Recursively scan subdirectories
                        subdirectory_images = self._scan_directory_worker(item)
                        image_files.extend(subdirectory_images)
                except (PermissionError, OSError) as e:
                    self.logger.warning(f"Cannot access {item}: {e}")
                    continue
                    
        except (PermissionError, OSError) as e:
            self.logger.warning(f"Cannot access directory {directory}: {e}")
        
        return image_files
    
    def scan_directory(self, root_directory: Path) -> List[Path]:
        """
        Recursively scan a directory for image files.
        
        Args:
            root_directory: Root directory to start scanning from
            
        Returns:
            List of unique image file paths found
        """
        self.logger.info(f"Starting scan of directory: {root_directory}")
        
        if not root_directory.exists():
            raise ValueError(f"Directory does not exist: {root_directory}")
        
        if not root_directory.is_dir():
            raise ValueError(f"Path is not a directory: {root_directory}")
        
        # Collect all subdirectories for parallel processing
        directories_to_scan = [root_directory]
        all_directories = []
        
        # Build list of all directories first
        while directories_to_scan:
            current_dir = directories_to_scan.pop(0)
            all_directories.append(current_dir)
            
            try:
                for item in current_dir.iterdir():
                    if item.is_dir() and not item.is_symlink():
                        # Skip directories that should be ignored
                        if not self._should_skip_directory(item):
                            directories_to_scan.append(item)
                        else:
                            self.logger.debug(f"Skipping directory during discovery: {item}")
            except (PermissionError, OSError) as e:
                self.logger.warning(f"Cannot list directory {current_dir}: {e}")
        
        # Process directories in parallel
        all_image_files = []
        
        if len(all_directories) == 1 or self.max_workers == 1:
            # Single-threaded processing for small directory sets
            all_image_files = self._scan_directory_worker(root_directory)
        else:
            # Multi-threaded processing
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit directory scanning tasks
                future_to_directory = {
                    executor.submit(self._scan_files_in_directory, directory): directory
                    for directory in all_directories
                }
                
                # Collect results
                for future in as_completed(future_to_directory):
                    directory = future_to_directory[future]
                    try:
                        directory_files = future.result()
                        all_image_files.extend(directory_files)
                    except Exception as e:
                        self.logger.warning(f"Error scanning directory {directory}: {e}")
        
        # Remove duplicates and sort
        unique_files = list(set(all_image_files))
        unique_files.sort()
        
        self.logger.info(f"Scan completed. Found {len(unique_files)} unique image files")
        return unique_files
    
    def _scan_files_in_directory(self, directory: Path) -> List[Path]:
        """
        Scan only files in a single directory (non-recursive).
        
        Args:
            directory: Directory to scan
            
        Returns:
            List of image files in the directory
        """
        image_files = []
        
        try:
            if not directory.exists() or not directory.is_dir():
                return image_files
            
            for item in directory.iterdir():
                try:
                    if item.is_file() and not item.is_symlink():
                        if self._is_image_file(item):
                            image_files.append(item.resolve())
                except (PermissionError, OSError) as e:
                    self.logger.debug(f"Cannot access file {item}: {e}")
                    continue
                    
        except (PermissionError, OSError) as e:
            self.logger.warning(f"Cannot access directory {directory}: {e}")
        
        return image_files
    
    def get_supported_extensions(self) -> Set[str]:
        """
        Get the set of supported image file extensions.
        
        Returns:
            Set of supported file extensions (including the dot)
        """
        return self.SUPPORTED_EXTENSIONS.copy()
    
    def get_supported_mime_types(self) -> Set[str]:
        """
        Get the set of supported image MIME types.
        
        Returns:
            Set of supported MIME types
        """
        return self.IMAGE_MIME_TYPES.copy()
