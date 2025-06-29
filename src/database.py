"""
Database module for storing and querying image metadata.
"""

import logging
import sqlite3
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from .metadata_extractor import ImageMetadata


class Database:
    """SQLite database for storing image metadata and analysis results."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to database file. If None, uses in-memory database.
        """
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        
        if db_path:
            self.connection = sqlite3.connect(str(db_path), check_same_thread=False)
            self.logger.info(f"Connected to persistent database: {db_path}")
        else:
            self.connection = sqlite3.connect(":memory:", check_same_thread=False)
            self.logger.info("Connected to in-memory database")
        
        self.connection.row_factory = sqlite3.Row
        self._create_tables()
    
    def _create_tables(self) -> None:
        """Create database tables for storing image metadata."""
        try:
            cursor = self.connection.cursor()
            
            # Main images table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT UNIQUE NOT NULL,
                    file_size INTEGER NOT NULL,
                    file_hash TEXT NOT NULL,
                    width INTEGER NOT NULL,
                    height INTEGER NOT NULL,
                    format TEXT,
                    timestamp TEXT,
                    camera_make TEXT,
                    camera_model TEXT,
                    gps_latitude REAL,
                    gps_longitude REAL,
                    perceptual_hash TEXT,
                    average_hash TEXT,
                    difference_hash TEXT,
                    wavelet_hash TEXT,
                    creation_time TEXT,
                    modification_time TEXT,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    marked_for_removal BOOLEAN DEFAULT FALSE,
                    is_protected BOOLEAN DEFAULT FALSE,
                    removal_reason TEXT
                )
            """)
            
            # Duplicate groups table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS duplicate_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_type TEXT NOT NULL,  -- 'timestamp', 'hash', 'perceptual'
                    similarity_score REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Mapping table for images in duplicate groups
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS group_images (
                    group_id INTEGER,
                    image_id INTEGER,
                    is_keeper BOOLEAN DEFAULT FALSE,
                    FOREIGN KEY (group_id) REFERENCES duplicate_groups (id),
                    FOREIGN KEY (image_id) REFERENCES images (id),
                    PRIMARY KEY (group_id, image_id)
                )
            """)
            
            # Create indexes for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_file_hash ON images (file_hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_timestamp ON images (timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_perceptual_hash ON images (perceptual_hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_dimensions ON images (width, height)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_camera ON images (camera_make, camera_model)")
            
            # Add columns for removal workflow if they don't exist
            cursor.execute("""
                ALTER TABLE images ADD COLUMN marked_for_removal BOOLEAN DEFAULT FALSE
            """)
            cursor.execute("""
                ALTER TABLE images ADD COLUMN is_protected BOOLEAN DEFAULT FALSE
            """)
            cursor.execute("""
                ALTER TABLE images ADD COLUMN removal_reason TEXT
            """)
            
            self.connection.commit()
            self.logger.debug("Database tables created successfully")
            
        except sqlite3.Error as e:
            # Ignore "duplicate column" errors when upgrading existing database
            if "duplicate column" not in str(e).lower():
                self.logger.error(f"Error creating database tables: {e}")
                raise
    
    @contextmanager
    def get_cursor(self):
        """Context manager for database cursors."""
        cursor = self.connection.cursor()
        try:
            yield cursor
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        finally:
            cursor.close()
    
    def store_image_metadata(self, file_path: Path, metadata: ImageMetadata) -> int:
        """
        Store image metadata in the database.
        
        Args:
            file_path: Path to the image file
            metadata: ImageMetadata object
            
        Returns:
            Database ID of the inserted record
        """
        try:
            with self.get_cursor() as cursor:
                # Extract GPS coordinates if available
                gps_lat = None
                gps_lon = None
                if metadata.gps_info:
                    gps_lat = metadata.gps_info.get('latitude')
                    gps_lon = metadata.gps_info.get('longitude')
                
                cursor.execute("""
                    INSERT OR REPLACE INTO images (
                        file_path, file_size, file_hash, width, height, format,
                        timestamp, camera_make, camera_model, gps_latitude, gps_longitude,
                        perceptual_hash, average_hash, difference_hash, wavelet_hash,
                        creation_time, modification_time
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(file_path),
                    metadata.file_size,
                    metadata.file_hash,
                    metadata.width,
                    metadata.height,
                    metadata.format,
                    metadata.timestamp.isoformat() if metadata.timestamp else None,
                    metadata.camera_make,
                    metadata.camera_model,
                    gps_lat,
                    gps_lon,
                    metadata.perceptual_hash,
                    metadata.average_hash,
                    metadata.difference_hash,
                    metadata.wavelet_hash,
                    metadata.creation_time.isoformat() if metadata.creation_time else None,
                    metadata.modification_time.isoformat() if metadata.modification_time else None
                ))
                
                return cursor.lastrowid or 0
                
        except sqlite3.Error as e:
            self.logger.error(f"Error storing metadata for {file_path}: {e}")
            raise
    
    def get_images_by_timestamp(self) -> Dict[str, List[sqlite3.Row]]:
        """
        Get images grouped by timestamp.
        
        Returns:
            Dictionary mapping timestamps to lists of image records
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute("""
                    SELECT * FROM images 
                    WHERE timestamp IS NOT NULL 
                    ORDER BY timestamp, file_path
                """)
                
                images_by_timestamp = {}
                for row in cursor.fetchall():
                    timestamp = row['timestamp']
                    if timestamp not in images_by_timestamp:
                        images_by_timestamp[timestamp] = []
                    images_by_timestamp[timestamp].append(row)
                
                # Filter to only groups with multiple images
                return {ts: imgs for ts, imgs in images_by_timestamp.items() if len(imgs) > 1}
                
        except sqlite3.Error as e:
            self.logger.error(f"Error querying images by timestamp: {e}")
            return {}
    
    def get_images_by_hash(self) -> Dict[str, List[sqlite3.Row]]:
        """
        Get images grouped by file hash.
        
        Returns:
            Dictionary mapping file hashes to lists of image records
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute("""
                    SELECT * FROM images 
                    WHERE file_hash != '' 
                    ORDER BY file_hash, file_path
                """)
                
                images_by_hash = {}
                for row in cursor.fetchall():
                    file_hash = row['file_hash']
                    if file_hash not in images_by_hash:
                        images_by_hash[file_hash] = []
                    images_by_hash[file_hash].append(row)
                
                # Filter to only groups with multiple images
                return {h: imgs for h, imgs in images_by_hash.items() if len(imgs) > 1}
                
        except sqlite3.Error as e:
            self.logger.error(f"Error querying images by hash: {e}")
            return {}
    
    def get_all_images(self) -> List[sqlite3.Row]:
        """
        Get all images from the database.
        
        Returns:
            List of all image records
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute("SELECT * FROM images ORDER BY file_path")
                return cursor.fetchall()
                
        except sqlite3.Error as e:
            self.logger.error(f"Error querying all images: {e}")
            return []
    
    def get_images_with_perceptual_hashes(self) -> List[sqlite3.Row]:
        """
        Get all images that have perceptual hashes.
        
        Returns:
            List of image records with perceptual hashes
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute("""
                    SELECT * FROM images 
                    WHERE perceptual_hash IS NOT NULL AND perceptual_hash != ''
                    ORDER BY file_path
                """)
                return cursor.fetchall()
                
        except sqlite3.Error as e:
            self.logger.error(f"Error querying images with perceptual hashes: {e}")
            return []
    
    def create_duplicate_group(self, group_type: str, similarity_score: Optional[float] = None) -> int:
        """
        Create a new duplicate group.
        
        Args:
            group_type: Type of duplicate detection ('timestamp', 'hash', 'perceptual')
            similarity_score: Similarity score for perceptual matches
            
        Returns:
            ID of the created group
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO duplicate_groups (group_type, similarity_score)
                    VALUES (?, ?)
                """, (group_type, similarity_score))
                
                return cursor.lastrowid or 0
                
        except sqlite3.Error as e:
            self.logger.error(f"Error creating duplicate group: {e}")
            raise
    
    def add_image_to_group(self, group_id: int, image_id: int, is_keeper: bool = False) -> None:
        """
        Add an image to a duplicate group.
        
        Args:
            group_id: ID of the duplicate group
            image_id: ID of the image
            is_keeper: Whether this image should be kept
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute("""
                    INSERT OR REPLACE INTO group_images (group_id, image_id, is_keeper)
                    VALUES (?, ?, ?)
                """, (group_id, image_id, is_keeper))
                
        except sqlite3.Error as e:
            self.logger.error(f"Error adding image to group: {e}")
            raise
    
    def get_duplicate_groups(self) -> List[Dict[str, Any]]:
        """
        Get all duplicate groups with their images.
        
        Returns:
            List of duplicate group dictionaries
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        dg.id as group_id,
                        dg.group_type,
                        dg.similarity_score,
                        i.id as image_id,
                        i.file_path,
                        i.file_size,
                        i.width,
                        i.height,
                        gi.is_keeper
                    FROM duplicate_groups dg
                    JOIN group_images gi ON dg.id = gi.group_id
                    JOIN images i ON gi.image_id = i.id
                    ORDER BY dg.id, gi.is_keeper DESC, i.file_path
                """)
                
                groups = {}
                for row in cursor.fetchall():
                    group_id = row['group_id']
                    if group_id not in groups:
                        groups[group_id] = {
                            'id': group_id,
                            'type': row['group_type'],
                            'similarity_score': row['similarity_score'],
                            'images': []
                        }
                    
                    groups[group_id]['images'].append({
                        'id': row['image_id'],
                        'file_path': row['file_path'],
                        'file_size': row['file_size'],
                        'width': row['width'],
                        'height': row['height'],
                        'is_keeper': bool(row['is_keeper'])
                    })
                
                return list(groups.values())
                
        except sqlite3.Error as e:
            self.logger.error(f"Error getting duplicate groups: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics.
        
        Returns:
            Dictionary with various statistics
        """
        try:
            with self.get_cursor() as cursor:
                stats = {}
                
                # Total images
                cursor.execute("SELECT COUNT(*) as count FROM images")
                stats['total_images'] = cursor.fetchone()['count']
                
                # Images with timestamps
                cursor.execute("SELECT COUNT(*) as count FROM images WHERE timestamp IS NOT NULL")
                stats['images_with_timestamps'] = cursor.fetchone()['count']
                
                # Images with perceptual hashes
                cursor.execute("""
                    SELECT COUNT(*) as count FROM images 
                    WHERE perceptual_hash IS NOT NULL AND perceptual_hash != ''
                """)
                stats['images_with_perceptual_hashes'] = cursor.fetchone()['count']
                
                # Total duplicate groups
                cursor.execute("SELECT COUNT(*) as count FROM duplicate_groups")
                stats['duplicate_groups'] = cursor.fetchone()['count']
                
                # Duplicate groups by type
                cursor.execute("""
                    SELECT group_type, COUNT(*) as count 
                    FROM duplicate_groups 
                    GROUP BY group_type
                """)
                stats['groups_by_type'] = {row['group_type']: row['count'] for row in cursor.fetchall()}
                
                return stats
                
        except sqlite3.Error as e:
            self.logger.error(f"Error getting statistics: {e}")
            return {}
    
    def close(self) -> None:
        """Close the database connection."""
        if self.connection:
            self.connection.close()
            self.logger.debug("Database connection closed")

    def mark_image_for_removal(self, image_id: int, reason: str = "duplicate") -> None:
        """
        Mark an image for removal.
        
        Args:
            image_id: ID of the image to mark for removal
            reason: Reason for removal (e.g., 'duplicate', 'similar')
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute("""
                    UPDATE images 
                    SET marked_for_removal = TRUE, removal_reason = ?
                    WHERE id = ? AND is_protected = FALSE
                """, (reason, image_id))
                
                if cursor.rowcount == 0:
                    self.logger.warning(f"Image {image_id} was not marked for removal (may be protected or not found)")
                else:
                    self.logger.debug(f"Marked image {image_id} for removal: {reason}")
                    
        except sqlite3.Error as e:
            self.logger.error(f"Error marking image {image_id} for removal: {e}")
            raise

    def mark_image_protected(self, file_path: str) -> bool:
        """
        Mark an image as protected from removal.
        
        Args:
            file_path: Path to the image file to protect
            
        Returns:
            True if image was successfully marked as protected
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute("""
                    UPDATE images 
                    SET is_protected = TRUE, marked_for_removal = FALSE, removal_reason = NULL
                    WHERE file_path = ?
                """, (file_path,))
                
                if cursor.rowcount == 0:
                    self.logger.warning(f"Image not found in database: {file_path}")
                    return False
                else:
                    self.logger.info(f"Protected image from removal: {file_path}")
                    return True
                    
        except sqlite3.Error as e:
            self.logger.error(f"Error protecting image {file_path}: {e}")
            raise

    def get_images_for_removal(self) -> List[Dict[str, Any]]:
        """
        Get all images marked for removal that are not protected.
        
        Returns:
            List of image dictionaries marked for removal
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute("""
                    SELECT id, file_path, file_size, removal_reason
                    FROM images 
                    WHERE marked_for_removal = TRUE AND is_protected = FALSE
                    ORDER BY file_path
                """)
                
                return [dict(row) for row in cursor.fetchall()]
                
        except sqlite3.Error as e:
            self.logger.error(f"Error getting images for removal: {e}")
            return []

    def unmark_image_for_removal(self, image_id: int) -> None:
        """
        Remove the removal mark from an image.
        
        Args:
            image_id: ID of the image to unmark
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute("""
                    UPDATE images 
                    SET marked_for_removal = FALSE, removal_reason = NULL
                    WHERE id = ?
                """, (image_id,))
                
        except sqlite3.Error as e:
            self.logger.error(f"Error unmarking image {image_id} for removal: {e}")
            raise

    def process_duplicate_groups_for_removal(self, duplicate_groups: List[Dict[str, Any]]) -> int:
        """
        Process duplicate groups and mark non-keeper images for removal.
        
        Args:
            duplicate_groups: List of duplicate group dictionaries
            
        Returns:
            Number of images marked for removal
        """
        marked_count = 0
        
        try:
            for group in duplicate_groups:
                group_type = group.get('type', 'unknown')
                
                # Mark all duplicates (non-keepers) for removal
                for duplicate in group.get('duplicates', []):
                    image_id = duplicate.get('id')
                    if image_id:
                        self.mark_image_for_removal(image_id, f"{group_type}_duplicate")
                        marked_count += 1
            
            self.logger.info(f"Marked {marked_count} images for removal from {len(duplicate_groups)} duplicate groups")
            return marked_count
            
        except Exception as e:
            self.logger.error(f"Error processing duplicate groups for removal: {e}")
            raise
