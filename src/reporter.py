"""
Report generation module for duplicate detection results.
"""

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from .duplicate_detector import DuplicateGroup


class Reporter:
    """Generates reports for duplicate detection results."""
    
    def __init__(self, output_dir: Path):
        """
        Initialize reporter.
        
        Args:
            output_dir: Directory to save reports
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
    
    def generate_report(self, duplicate_groups: List[DuplicateGroup], format_type: str = 'text') -> Path:
        """
        Generate a report of duplicate groups.
        
        Args:
            duplicate_groups: List of DuplicateGroup objects
            format_type: Report format ('text', 'csv', 'json')
            
        Returns:
            Path to the generated report file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format_type == 'text':
            return self._generate_text_report(duplicate_groups, timestamp)
        elif format_type == 'csv':
            return self._generate_csv_report(duplicate_groups, timestamp)
        elif format_type == 'json':
            return self._generate_json_report(duplicate_groups, timestamp)
        else:
            raise ValueError(f"Unsupported report format: {format_type}")
    
    def _generate_text_report(self, duplicate_groups: List[DuplicateGroup], timestamp: str) -> Path:
        """Generate a human-readable text report."""
        report_path = self.output_dir / f"duplicate_report_{timestamp}.txt"
        
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write("OmniDupe - Duplicate Image Detection Report\n")
                f.write("=" * 50 + "\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total duplicate groups found: {len(duplicate_groups)}\n\n")
                
                # Summary statistics
                total_duplicates = sum(len(group.get_duplicates()) for group in duplicate_groups)
                total_size_saved = sum(group.to_dict()['total_size_saved'] for group in duplicate_groups)
                
                f.write("Summary:\n")
                f.write(f"  Total images that can be removed: {total_duplicates}\n")
                f.write(f"  Total disk space that can be saved: {self._format_size(total_size_saved)}\n\n")
                
                # Group by detection method
                groups_by_type = {}
                for group in duplicate_groups:
                    group_type = group.type
                    if group_type not in groups_by_type:
                        groups_by_type[group_type] = []
                    groups_by_type[group_type].append(group)
                
                for group_type, groups in groups_by_type.items():
                    f.write(f"\n{group_type.upper()} DUPLICATES ({len(groups)} groups)\n")
                    f.write("-" * 40 + "\n")
                    
                    for i, group in enumerate(groups, 1):
                        group_data = group.to_dict()
                        f.write(f"\nGroup {i} ({group_data['total_images']} images, "
                               f"save {self._format_size(group_data['total_size_saved'])}):\n")
                        
                        if group.similarity_score is not None:
                            f.write(f"  Similarity score: {group.similarity_score:.2f}\n")
                        
                        f.write(f"  KEEP: {group_data['keeper']['file_path']}\n")
                        f.write(f"        Size: {self._format_size(group_data['keeper']['file_size'])}, "
                               f"Resolution: {group_data['keeper']['width']}x{group_data['keeper']['height']}\n")
                        
                        f.write("  REMOVE:\n")
                        for duplicate in group_data['duplicates']:
                            f.write(f"    - {duplicate['file_path']}\n")
                            f.write(f"      Size: {self._format_size(duplicate['file_size'])}, "
                                   f"Resolution: {duplicate['width']}x{duplicate['height']}\n")
                
                # Final summary
                f.write(f"\n" + "=" * 50 + "\n")
                f.write("SUMMARY OF ACTIONS:\n")
                f.write(f"Files to keep: {len(duplicate_groups)}\n")
                f.write(f"Files to remove: {total_duplicates}\n")
                f.write(f"Disk space to save: {self._format_size(total_size_saved)}\n")
                
        except Exception as e:
            self.logger.error(f"Error generating text report: {e}")
            raise
        
        self.logger.info(f"Text report generated: {report_path}")
        return report_path
    
    def _generate_csv_report(self, duplicate_groups: List[DuplicateGroup], timestamp: str) -> Path:
        """Generate a CSV report suitable for spreadsheet analysis."""
        report_path = self.output_dir / f"duplicate_report_{timestamp}.csv"
        
        try:
            with open(report_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Write header
                writer.writerow([
                    'Group ID', 'Detection Method', 'Similarity Score', 'Action',
                    'File Path', 'File Size (bytes)', 'File Size (human)', 
                    'Width', 'Height', 'Resolution (total pixels)'
                ])
                
                group_id = 1
                for group in duplicate_groups:
                    group_data = group.to_dict()
                    
                    # Write keeper row
                    keeper = group_data['keeper']
                    writer.writerow([
                        group_id,
                        group.type,
                        group.similarity_score if group.similarity_score else '',
                        'KEEP',
                        keeper['file_path'],
                        keeper['file_size'],
                        self._format_size(keeper['file_size']),
                        keeper['width'],
                        keeper['height'],
                        keeper['width'] * keeper['height']
                    ])
                    
                    # Write duplicate rows
                    for duplicate in group_data['duplicates']:
                        writer.writerow([
                            group_id,
                            group.type,
                            group.similarity_score if group.similarity_score else '',
                            'REMOVE',
                            duplicate['file_path'],
                            duplicate['file_size'],
                            self._format_size(duplicate['file_size']),
                            duplicate['width'],
                            duplicate['height'],
                            duplicate['width'] * duplicate['height']
                        ])
                    
                    group_id += 1
                    
        except Exception as e:
            self.logger.error(f"Error generating CSV report: {e}")
            raise
        
        self.logger.info(f"CSV report generated: {report_path}")
        return report_path
    
    def _generate_json_report(self, duplicate_groups: List[DuplicateGroup], timestamp: str) -> Path:
        """Generate a JSON report for programmatic analysis."""
        report_path = self.output_dir / f"duplicate_report_{timestamp}.json"
        
        try:
            # Prepare data structure
            report_data = {
                'metadata': {
                    'generated_at': datetime.now().isoformat(),
                    'total_groups': len(duplicate_groups),
                    'total_duplicates': sum(len(group.get_duplicates()) for group in duplicate_groups),
                    'total_size_saved': sum(group.to_dict()['total_size_saved'] for group in duplicate_groups)
                },
                'duplicate_groups': []
            }
            
            for i, group in enumerate(duplicate_groups):
                group_data = group.to_dict()
                group_entry = {
                    'group_id': i + 1,
                    'detection_method': group.type,
                    'similarity_score': group.similarity_score,
                    'total_images': group_data['total_images'],
                    'total_size_saved': group_data['total_size_saved'],
                    'keeper': {
                        'file_path': group_data['keeper']['file_path'],
                        'file_size': group_data['keeper']['file_size'],
                        'width': group_data['keeper']['width'],
                        'height': group_data['keeper']['height'],
                        'resolution': group_data['keeper']['width'] * group_data['keeper']['height']
                    },
                    'duplicates': []
                }
                
                for duplicate in group_data['duplicates']:
                    group_entry['duplicates'].append({
                        'file_path': duplicate['file_path'],
                        'file_size': duplicate['file_size'],
                        'width': duplicate['width'],
                        'height': duplicate['height'],
                        'resolution': duplicate['width'] * duplicate['height']
                    })
                
                report_data['duplicate_groups'].append(group_entry)
            
            # Write JSON file
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            self.logger.error(f"Error generating JSON report: {e}")
            raise
        
        self.logger.info(f"JSON report generated: {report_path}")
        return report_path
    
    def generate_summary_report(self, duplicate_groups: List[DuplicateGroup]) -> str:
        """
        Generate a brief summary string for console output.
        
        Args:
            duplicate_groups: List of DuplicateGroup objects
            
        Returns:
            Summary string
        """
        if not duplicate_groups:
            return "No duplicates found."
        
        total_groups = len(duplicate_groups)
        total_duplicates = sum(len(group.get_duplicates()) for group in duplicate_groups)
        total_size_saved = sum(group.to_dict()['total_size_saved'] for group in duplicate_groups)
        
        # Group by type
        groups_by_type = {}
        for group in duplicate_groups:
            group_type = group.type
            groups_by_type[group_type] = groups_by_type.get(group_type, 0) + 1
        
        summary_lines = [
            f"Found {total_groups} duplicate groups:",
            f"  - {total_duplicates} files can be removed",
            f"  - {self._format_size(total_size_saved)} disk space can be saved",
            "",
            "Detection methods used:"
        ]
        
        for group_type, count in groups_by_type.items():
            summary_lines.append(f"  - {group_type}: {count} groups")
        
        return "\n".join(summary_lines)
    
    def _format_size(self, size_bytes: int) -> str:
        """
        Format file size in human-readable format.
        
        Args:
            size_bytes: Size in bytes
            
        Returns:
            Formatted size string
        """
        if size_bytes == 0:
            return "0 B"
        
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        size = float(size_bytes)
        unit_index = 0
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        if unit_index == 0:
            return f"{int(size)} {units[unit_index]}"
        else:
            return f"{size:.1f} {units[unit_index]}"
