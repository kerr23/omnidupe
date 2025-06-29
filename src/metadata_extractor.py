"""
Metadata extraction module for image files.
"""

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import imagehash
from PIL import Image, ExifTags
from PIL.ExifTags import TAGS
import exifread


class ImageMetadata:
    """Container for image metadata."""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.file_size = 0
        self.file_hash = ""
        self.width = 0
        self.height = 0
        self.format = ""
        self.timestamp = None
        self.camera_make = ""
        self.camera_model = ""
        self.gps_info = None
        self.perceptual_hash = ""
        self.average_hash = ""
        self.difference_hash = ""
        self.wavelet_hash = ""
        self.creation_time = None
        self.modification_time = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            'file_path': str(self.file_path),
            'file_size': self.file_size,
            'file_hash': self.file_hash,
            'width': self.width,
            'height': self.height,
            'format': self.format,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'camera_make': self.camera_make,
            'camera_model': self.camera_model,
            'gps_info': self.gps_info,
            'perceptual_hash': self.perceptual_hash,
            'average_hash': self.average_hash,
            'difference_hash': self.difference_hash,
            'wavelet_hash': self.wavelet_hash,
            'creation_time': self.creation_time.isoformat() if self.creation_time else None,
            'modification_time': self.modification_time.isoformat() if self.modification_time else None
        }


class MetadataExtractor:
    """Extracts metadata from image files."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def extract_metadata(self, file_path: Path) -> ImageMetadata:
        """
        Extract comprehensive metadata from an image file.
        
        Args:
            file_path: Path to the image file
            
        Returns:
            ImageMetadata object containing extracted metadata
        """
        metadata = ImageMetadata(file_path)
        
        try:
            # Get file system metadata
            stat_info = file_path.stat()
            metadata.file_size = stat_info.st_size
            metadata.creation_time = datetime.fromtimestamp(stat_info.st_ctime)
            metadata.modification_time = datetime.fromtimestamp(stat_info.st_mtime)
            
            # Calculate file hash
            metadata.file_hash = self._calculate_file_hash(file_path)
            
            # Extract image metadata using PIL
            self._extract_pil_metadata(file_path, metadata)
            
            # Extract EXIF data using exifread as fallback
            self._extract_exif_metadata(file_path, metadata)
            
            # Calculate perceptual hashes
            self._calculate_perceptual_hashes(file_path, metadata)
            
        except Exception as e:
            self.logger.warning(f"Error extracting metadata from {file_path}: {e}")
        
        return metadata
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """
        Calculate SHA-256 hash of the image file content.
        
        Args:
            file_path: Path to the image file
            
        Returns:
            Hexadecimal hash string
        """
        hasher = hashlib.sha256()
        
        try:
            with open(file_path, 'rb') as f:
                # Read file in chunks to handle large files efficiently
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            self.logger.warning(f"Error calculating hash for {file_path}: {e}")
            return ""
    
    def _extract_pil_metadata(self, file_path: Path, metadata: ImageMetadata) -> None:
        """
        Extract metadata using PIL/Pillow.
        
        Args:
            file_path: Path to the image file
            metadata: ImageMetadata object to populate
        """
        try:
            with Image.open(file_path) as img:
                metadata.width, metadata.height = img.size
                metadata.format = img.format or ""
                
                # Extract EXIF data if available
                if hasattr(img, '_getexif') and img._getexif() is not None:
                    exif_data = img._getexif()
                    self._parse_exif_data(exif_data, metadata)
                
                # Try alternative EXIF extraction method
                if hasattr(img, 'getexif'):
                    exif_data = img.getexif()
                    if exif_data:
                        self._parse_exif_data(exif_data, metadata)
                
        except Exception as e:
            self.logger.debug(f"PIL metadata extraction failed for {file_path}: {e}")
    
    def _parse_exif_data(self, exif_data: Dict, metadata: ImageMetadata) -> None:
        """
        Parse EXIF data and populate metadata.
        
        Args:
            exif_data: EXIF data dictionary
            metadata: ImageMetadata object to populate
        """
        try:
            for tag_id, value in exif_data.items():
                tag_name = TAGS.get(tag_id, tag_id)
                
                if tag_name == 'DateTime' or tag_name == 'DateTimeOriginal':
                    try:
                        metadata.timestamp = datetime.strptime(str(value), '%Y:%m:%d %H:%M:%S')
                    except (ValueError, TypeError):
                        pass
                
                elif tag_name == 'Make':
                    metadata.camera_make = str(value).strip()
                
                elif tag_name == 'Model':
                    metadata.camera_model = str(value).strip()
                
                elif tag_name == 'GPSInfo':
                    metadata.gps_info = self._parse_gps_info(value)
                    
        except Exception as e:
            self.logger.debug(f"Error parsing EXIF data: {e}")
    
    def _parse_gps_info(self, gps_data: Dict) -> Optional[Dict[str, float]]:
        """
        Parse GPS information from EXIF data.
        
        Args:
            gps_data: GPS data from EXIF
            
        Returns:
            Dictionary with latitude and longitude, or None if parsing fails
        """
        try:
            if not gps_data:
                return None
            
            # This is a simplified GPS parser
            # In practice, GPS data extraction can be quite complex
            lat = gps_data.get(2)  # GPSLatitude
            lat_ref = gps_data.get(1)  # GPSLatitudeRef
            lon = gps_data.get(4)  # GPSLongitude
            lon_ref = gps_data.get(3)  # GPSLongitudeRef
            
            if lat and lon and lat_ref and lon_ref:
                # Convert from degrees, minutes, seconds to decimal degrees
                lat_decimal = self._dms_to_decimal(lat, lat_ref)
                lon_decimal = self._dms_to_decimal(lon, lon_ref)
                
                if lat_decimal is not None and lon_decimal is not None:
                    return {'latitude': lat_decimal, 'longitude': lon_decimal}
                    
        except Exception as e:
            self.logger.debug(f"Error parsing GPS info: {e}")
        
        return None
    
    def _dms_to_decimal(self, dms_tuple: Tuple, ref: str) -> Optional[float]:
        """
        Convert degrees, minutes, seconds to decimal degrees.
        
        Args:
            dms_tuple: Tuple of (degrees, minutes, seconds)
            ref: Reference direction (N, S, E, W)
            
        Returns:
            Decimal degrees, or None if conversion fails
        """
        try:
            if len(dms_tuple) != 3:
                return None
            
            degrees = float(dms_tuple[0])
            minutes = float(dms_tuple[1])
            seconds = float(dms_tuple[2])
            
            decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
            
            if ref.upper() in ['S', 'W']:
                decimal = -decimal
            
            return decimal
            
        except (ValueError, TypeError, IndexError):
            return None
    
    def _extract_exif_metadata(self, file_path: Path, metadata: ImageMetadata) -> None:
        """
        Extract EXIF metadata using exifread library as fallback.
        
        Args:
            file_path: Path to the image file
            metadata: ImageMetadata object to populate
        """
        try:
            with open(file_path, 'rb') as f:
                tags = exifread.process_file(f, stop_tag='EXIF DateTimeOriginal')
                
                # Try to get timestamp if not already extracted
                if not metadata.timestamp:
                    for tag_name in ['EXIF DateTimeOriginal', 'Image DateTime']:
                        if tag_name in tags:
                            try:
                                timestamp_str = str(tags[tag_name])
                                metadata.timestamp = datetime.strptime(timestamp_str, '%Y:%m:%d %H:%M:%S')
                                break
                            except (ValueError, TypeError):
                                pass
                
                # Get camera info if not already extracted
                if not metadata.camera_make and 'Image Make' in tags:
                    metadata.camera_make = str(tags['Image Make']).strip()
                
                if not metadata.camera_model and 'Image Model' in tags:
                    metadata.camera_model = str(tags['Image Model']).strip()
                    
        except Exception as e:
            self.logger.debug(f"ExifRead metadata extraction failed for {file_path}: {e}")
    
    def _calculate_perceptual_hashes(self, file_path: Path, metadata: ImageMetadata) -> None:
        """
        Calculate various perceptual hashes for the image.
        
        Args:
            file_path: Path to the image file
            metadata: ImageMetadata object to populate
        """
        try:
            with Image.open(file_path) as img:
                # Convert to RGB if necessary
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Calculate different types of perceptual hashes
                metadata.perceptual_hash = str(imagehash.phash(img))
                metadata.average_hash = str(imagehash.average_hash(img))
                metadata.difference_hash = str(imagehash.dhash(img))
                metadata.wavelet_hash = str(imagehash.whash(img))
                
        except Exception as e:
            self.logger.debug(f"Perceptual hash calculation failed for {file_path}: {e}")
    
    def get_image_dimensions(self, file_path: Path) -> Tuple[int, int]:
        """
        Get image dimensions without loading the full image.
        
        Args:
            file_path: Path to the image file
            
        Returns:
            Tuple of (width, height)
        """
        try:
            with Image.open(file_path) as img:
                return img.size
        except Exception as e:
            self.logger.warning(f"Could not get dimensions for {file_path}: {e}")
            return (0, 0)
