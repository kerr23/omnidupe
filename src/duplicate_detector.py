"""
Duplicate detection module using multi-stage strategy.
"""

import logging
from typing import List, Dict, Any, Set, Tuple
from pathlib import Path

import imagehash

from .database import Database


class DuplicateGroup:
    """Represents a group of duplicate or similar images."""
    
    def __init__(self, group_type: str, similarity_score: float = None):
        self.type = group_type  # 'timestamp', 'hash', 'perceptual'
        self.similarity_score = similarity_score
        self.images = []
        self.keeper = None
    
    def add_image(self, image_info: Dict[str, Any]) -> None:
        """Add an image to this group."""
        self.images.append(image_info)
    
    def select_keeper(self) -> Dict[str, Any]:
        """
        Select which image to keep based on criteria:
        1. Highest resolution (width × height)
        2. Largest file size
        3. Simplest filename (shortest, then lexicographical)
        
        Returns:
            Image info dictionary for the selected keeper
        """
        if not self.images:
            return None
        
        if len(self.images) == 1:
            self.keeper = self.images[0]
            return self.keeper
        
        # Sort by criteria: resolution desc, file size desc, filename asc
        sorted_images = sorted(
            self.images,
            key=lambda img: (
                -(img['width'] * img['height']),  # Negative for descending
                -img['file_size'],                # Negative for descending
                len(Path(img['file_path']).name), # Ascending for simplest name
                img['file_path']                  # Ascending lexicographical
            )
        )
        
        self.keeper = sorted_images[0]
        return self.keeper
    
    def get_duplicates(self) -> List[Dict[str, Any]]:
        """Get list of images to be removed (all except keeper)."""
        if not self.keeper:
            self.select_keeper()
        
        return [img for img in self.images if img != self.keeper]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert group to dictionary for reporting."""
        if not self.keeper:
            self.select_keeper()
        
        return {
            'type': self.type,
            'similarity_score': self.similarity_score,
            'keeper': self.keeper,
            'duplicates': self.get_duplicates(),
            'total_images': len(self.images),
            'total_size_saved': sum(img['file_size'] for img in self.get_duplicates())
        }


class DuplicateDetector:
    """Detects duplicate and similar images using multi-stage strategy."""
    
    def __init__(self, database: Database, similarity_threshold: int = 5):
        """
        Initialize duplicate detector.
        
        Args:
            database: Database instance for querying image metadata
            similarity_threshold: Hamming distance threshold for perceptual similarity
        """
        self.database = database
        self.similarity_threshold = similarity_threshold
        self.logger = logging.getLogger(__name__)
    
    def find_duplicates(self) -> List[DuplicateGroup]:
        """
        Find all duplicate and similar images using multi-stage strategy.
        
        Returns:
            List of DuplicateGroup objects
        """
        self.logger.info("Starting duplicate detection process")
        
        duplicate_groups = []
        processed_images = set()
        
        # Stage 1: Find exact timestamp matches
        timestamp_groups = self._find_timestamp_duplicates(processed_images)
        duplicate_groups.extend(timestamp_groups)
        self.logger.info(f"Found {len(timestamp_groups)} timestamp-based duplicate groups")
        
        # Stage 2: Find file hash matches (exact content duplicates)
        hash_groups = self._find_hash_duplicates(processed_images)
        duplicate_groups.extend(hash_groups)
        self.logger.info(f"Found {len(hash_groups)} hash-based duplicate groups")
        
        # Stage 3: Find perceptual similarity matches
        perceptual_groups = self._find_perceptual_duplicates(processed_images)
        duplicate_groups.extend(perceptual_groups)
        self.logger.info(f"Found {len(perceptual_groups)} perceptual similarity groups")
        
        # Store results in database
        self._store_duplicate_groups(duplicate_groups)
        
        self.logger.info(f"Total duplicate groups found: {len(duplicate_groups)}")
        return duplicate_groups
    
    def _find_timestamp_duplicates(self, processed_images: Set[str]) -> List[DuplicateGroup]:
        """
        Find duplicates based on identical timestamps.
        
        Args:
            processed_images: Set of already processed image paths
            
        Returns:
            List of DuplicateGroup objects
        """
        groups = []
        images_by_timestamp = self.database.get_images_by_timestamp()
        
        for timestamp, images in images_by_timestamp.items():
            if len(images) < 2:
                continue
            
            # Filter out already processed images
            unprocessed_images = [
                img for img in images 
                if img['file_path'] not in processed_images
            ]
            
            if len(unprocessed_images) < 2:
                continue
            
            group = DuplicateGroup('timestamp')
            for image in unprocessed_images:
                group.add_image(dict(image))
                processed_images.add(image['file_path'])
            
            groups.append(group)
        
        return groups
    
    def _find_hash_duplicates(self, processed_images: Set[str]) -> List[DuplicateGroup]:
        """
        Find duplicates based on identical file hashes.
        
        Args:
            processed_images: Set of already processed image paths
            
        Returns:
            List of DuplicateGroup objects
        """
        groups = []
        images_by_hash = self.database.get_images_by_hash()
        
        for file_hash, images in images_by_hash.items():
            if len(images) < 2:
                continue
            
            # Filter out already processed images
            unprocessed_images = [
                img for img in images 
                if img['file_path'] not in processed_images
            ]
            
            if len(unprocessed_images) < 2:
                continue
            
            group = DuplicateGroup('hash')
            for image in unprocessed_images:
                group.add_image(dict(image))
                processed_images.add(image['file_path'])
            
            groups.append(group)
        
        return groups
    
    def _find_perceptual_duplicates(self, processed_images: Set[str]) -> List[DuplicateGroup]:
        """
        Find similar images based on perceptual hashing.
        
        Args:
            processed_images: Set of already processed image paths
            
        Returns:
            List of DuplicateGroup objects
        """
        groups = []
        images = self.database.get_images_with_perceptual_hashes()
        
        self.logger.debug(f"Found {len(images)} images with perceptual hashes in database")
        
        # Filter out already processed images
        unprocessed_images = [
            img for img in images 
            if img['file_path'] not in processed_images
        ]
        
        self.logger.debug(f"After filtering processed images: {len(unprocessed_images)} unprocessed images")
        
        if len(unprocessed_images) < 2:
            self.logger.debug("Not enough unprocessed images for perceptual comparison")
            return groups
        
        # Convert hash strings back to imagehash objects for comparison
        image_hashes = []
        for image in unprocessed_images:
            try:
                # Try different hash types
                hash_obj = None
                for hash_field in ['perceptual_hash', 'average_hash', 'difference_hash']:
                    # Use proper Row indexing instead of .get()
                    try:
                        hash_str = image[hash_field]
                    except (IndexError, KeyError):
                        hash_str = None
                        
                    if hash_str:
                        try:
                            hash_obj = imagehash.hex_to_hash(hash_str)
                            self.logger.debug(f"Successfully parsed {hash_field} for {image['file_path']}: {hash_str}")
                            break
                        except ValueError as ve:
                            self.logger.debug(f"Failed to parse {hash_field} for {image['file_path']}: {ve}")
                            continue
                
                if hash_obj is not None:
                    image_hashes.append((image, hash_obj))
                    self.logger.debug(f"Added image hash for {image['file_path']}")
                else:
                    self.logger.debug(f"No valid hash found for {image['file_path']}")
                    
            except Exception as e:
                self.logger.debug(f"Error processing hash for {image['file_path']}: {e}")
        
        self.logger.debug(f"Total images with valid hashes: {len(image_hashes)}")
        
        # Compare all pairs to find similar images
        similarity_groups = self._cluster_similar_images(image_hashes)
        
        self.logger.debug(f"Clustering found {len(similarity_groups)} similarity groups")
        
        for similar_images in similarity_groups:
            if len(similar_images) < 2:
                continue
            
            # Calculate average similarity score for the group
            similarities = []
            for i in range(len(similar_images)):
                for j in range(i + 1, len(similar_images)):
                    _, hash1 = similar_images[i]
                    _, hash2 = similar_images[j]
                    similarities.append(hash1 - hash2)  # Hamming distance
            
            avg_similarity = sum(similarities) / len(similarities) if similarities else 0
            
            group = DuplicateGroup('perceptual', avg_similarity)
            for image, _ in similar_images:
                group.add_image(dict(image))
                processed_images.add(image['file_path'])
            
            groups.append(group)
        
        return groups
    
    def _cluster_similar_images(self, image_hashes: List[Tuple]) -> List[List[Tuple]]:
        """
        Cluster images by perceptual similarity using simple threshold-based grouping.
        
        Args:
            image_hashes: List of (image_info, hash_object) tuples
            
        Returns:
            List of groups, where each group is a list of similar (image_info, hash_object) tuples
        """
        if not image_hashes:
            self.logger.debug("No image hashes provided for clustering")
            return []
        
        self.logger.debug(f"Clustering {len(image_hashes)} images with similarity threshold {self.similarity_threshold}")
        
        groups = []
        remaining = image_hashes.copy()
        
        while remaining:
            # Start new group with first remaining image
            current_group = [remaining.pop(0)]
            current_image, current_hash = current_group[0]
            
            self.logger.debug(f"Starting new cluster with {current_image['file_path']}")
            
            # Find all images similar to the current group
            i = 0
            while i < len(remaining):
                other_image, other_hash = remaining[i]
                
                # Check if this image is similar to any image in current group
                is_similar = False
                for _, group_hash in current_group:
                    hamming_distance = current_hash - other_hash
                    self.logger.debug(f"Comparing {current_image['file_path']} vs {other_image['file_path']}: distance = {hamming_distance}")
                    
                    if hamming_distance <= self.similarity_threshold:
                        is_similar = True
                        self.logger.debug(f"Images are similar (distance {hamming_distance} <= {self.similarity_threshold})")
                        break
                
                if is_similar:
                    current_group.append(remaining.pop(i))
                    self.logger.debug(f"Added {other_image['file_path']} to current group")
                else:
                    i += 1
            
            # Only keep groups with multiple images
            if len(current_group) > 1:
                self.logger.debug(f"Group has {len(current_group)} images, keeping it")
                groups.append(current_group)
            else:
                self.logger.debug(f"Group has only 1 image, discarding it")
        
        return groups
    
    def _store_duplicate_groups(self, duplicate_groups: List[DuplicateGroup]) -> None:
        """
        Store duplicate groups in the database.
        
        Args:
            duplicate_groups: List of DuplicateGroup objects
        """
        try:
            for group in duplicate_groups:
                # Create group record
                group_id = self.database.create_duplicate_group(
                    group.type, 
                    group.similarity_score
                )
                
                # Select keeper
                keeper = group.select_keeper()
                
                # Add images to group
                for image in group.images:
                    # Find image ID by file path
                    all_images = self.database.get_all_images()
                    image_id = None
                    for db_image in all_images:
                        if db_image['file_path'] == image['file_path']:
                            image_id = db_image['id']
                            break
                    
                    if image_id:
                        is_keeper = (image == keeper)
                        self.database.add_image_to_group(group_id, image_id, is_keeper)
                        
        except Exception as e:
            self.logger.error(f"Error storing duplicate groups: {e}")
    
    def get_detection_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the duplicate detection process.
        
        Returns:
            Dictionary with detection statistics
        """
        return self.database.get_statistics()
