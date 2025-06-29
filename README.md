# OmniDupe - Duplicate Image Finder

A Python application that recursively searches directories for duplicate and visually similar images using metadata analysis, file content hashing, and perceptual hashing.

## Features

- **Multi-stage Duplicate Detection**:
  - Primary: Timestamp metadata matching (EXIF DateTimeOriginal, CreateDate)
  - Secondary: File content hash matching (SHA-256)
  - Tertiary: Perceptual similarity using multiple hash algorithms (pHash, aHash, dHash, wHash)

- **Intelligent File Selection**: Automatically chooses which file to keep based on:
  - Highest resolution (width × height)
  - Largest file size (if resolution is identical)
  - Simplest filename (shortest length, then lexicographical order)

- **Comprehensive Reporting**: Generates reports in multiple formats:
  - Human-readable text format
  - CSV format for spreadsheet analysis
  - JSON format for programmatic processing

- **Safe Operation**:
  - Dry-run mode for testing without file deletion
  - User confirmation required for file removal
  - Backup script generation for manual review

- **Performance Optimized**:
  - Parallel processing for I/O-bound operations
  - SQLite database for efficient metadata storage and querying
  - Configurable worker thread limits

- **Docker Support**: Fully containerized with volume mounting for safe operation

## Installation

### Local Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd omnidupe
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

### Docker Installation

Build the Docker image:
```bash
docker build -t omnidupe .
```

## Usage

### Local Usage

Basic usage:
```bash
python main.py --input-dir /path/to/images --output-dir /path/to/results
```

Advanced usage:
```bash
python main.py \
  --input-dir /path/to/images \
  --output-dir /path/to/results \
  --remove-duplicates \
  --dry-run \
  --similarity-threshold 5 \
  --report-format json \
  --verbose
```

### Docker Usage

Basic scan (read-only):
```bash
docker run --rm \
  -v /path/to/images:/images:ro \
  -v /path/to/output:/data \
  omnidupe \
  --input-dir /images \
  --output-dir /data
```

Scan with duplicate removal:
```bash
docker run --rm \
  -v /path/to/images:/images \
  -v /path/to/output:/data \
  omnidupe \
  --input-dir /images \
  --output-dir /data \
  --remove-duplicates \
  --dry-run
```

Using environment variables:
```bash
docker run --rm \
  -e INPUT_DIR=/images \
  -e OUTPUT_DIR=/data \
  -v /path/to/images:/images:ro \
  -v /path/to/output:/data \
  omnidupe \
  --verbose
```

## Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--input-dir`, `-i` | Directory to scan for images | `$INPUT_DIR` |
| `--output-dir`, `-o` | Directory to store reports and database | `./output` or `$OUTPUT_DIR` |
| `--remove-duplicates` | Remove duplicate files after generating report | `False` |
| `--dry-run` | Show what would be deleted without actually deleting | `False` |
| `--similarity-threshold` | Hamming distance threshold for perceptual similarity | `10` |
| `--report-format` | Output report format (`text`, `csv`, `json`) | `text` |
| `--persistent-db` | Keep database file for future runs | `False` |
| `--verbose`, `-v` | Enable verbose logging | `False` |
| `--max-workers` | Maximum number of worker threads | `4` |

## Supported Image Formats

- JPEG (.jpg, .jpeg, .jfif, .pjpeg, .pjp)
- PNG (.png)
- GIF (.gif)
- TIFF (.tiff, .tif)
- BMP (.bmp)
- WebP (.webp)
- ICO (.ico)

## Detection Methods

### 1. Timestamp-based Detection
- Extracts EXIF timestamp metadata (DateTimeOriginal, CreateDate)
- Groups images with identical timestamps
- Most reliable for photos from digital cameras

### 2. Content Hash Detection
- Calculates SHA-256 hash of file content
- Identifies byte-for-byte identical files
- Useful for exact copies, even with different filenames

### 3. Perceptual Similarity Detection
- Uses multiple perceptual hashing algorithms:
  - pHash (perceptual hash): Robust to minor changes
  - aHash (average hash): Fast, good for basic similarity
  - dHash (difference hash): Sensitive to edges and gradients
  - wHash (wavelet hash): Advanced frequency domain analysis
- Configurable similarity threshold (Hamming distance)
- Groups visually similar images (e.g., different resolutions, slight edits)

## Output Files

The application generates several output files in the specified output directory:

- **Report file**: `duplicate_report_YYYYMMDD_HHMMSS.{txt|csv|json}`
- **Database file**: `omnidupe.db` (if `--persistent-db` is used)
- **Removal script**: `remove_duplicates.sh` (when duplicates are found)

## Example Output

```
OmniDupe - Duplicate Image Detection Report
==================================================
Generated: 2025-06-28 10:30:45
Total duplicate groups found: 3

Summary:
  Total images that can be removed: 7
  Total disk space that can be saved: 45.2 MB

TIMESTAMP DUPLICATES (2 groups)
----------------------------------------

Group 1 (3 images, save 12.8 MB):
  KEEP: /photos/vacation/IMG_001.jpg
        Size: 8.5 MB, Resolution: 4032x3024
  REMOVE:
    - /photos/backup/IMG_001_copy.jpg
      Size: 8.5 MB, Resolution: 4032x3024
    - /photos/duplicates/vacation_001.jpg
      Size: 4.3 MB, Resolution: 2016x1512

PERCEPTUAL DUPLICATES (1 group)
----------------------------------------

Group 2 (5 images, save 32.4 MB):
  Similarity score: 3.20
  KEEP: /photos/family/portrait_hires.jpg
        Size: 15.2 MB, Resolution: 6000x4000
  REMOVE:
    - /photos/family/portrait_med.jpg
      Size: 8.1 MB, Resolution: 3000x2000
    - /photos/family/portrait_small.jpg
      Size: 2.3 MB, Resolution: 1500x1000
    [...]
```

## Safety Features

- **Dry-run mode**: Test operations without making changes
- **User confirmation**: Requires explicit confirmation before deleting files
- **Backup scripts**: Generates shell scripts for manual review and execution
- **Read-only Docker volumes**: Mount image directories as read-only for safety
- **Comprehensive logging**: Detailed logs of all operations
- **Keeper verification**: Ensures selected files to keep are still accessible

## Performance Considerations

- **Parallel processing**: Configurable worker threads for I/O operations
- **Database indexing**: Optimized database queries with proper indexing
- **Memory efficiency**: Processes images in streams to minimize memory usage
- **Incremental processing**: Database persistence allows resuming interrupted operations
- **Batch operations**: Groups database operations for better performance

## Troubleshooting

### Common Issues

1. **Permission errors**: Ensure the application has read access to image directories and write access to output directory
2. **Memory issues**: Reduce `--max-workers` for systems with limited RAM
3. **Large directories**: Use `--persistent-db` for very large image collections
4. **False positives**: Adjust `--similarity-threshold` (higher values = less sensitive)

### Docker Issues

1. **Volume mounting**: Ensure correct host path mapping
2. **Permissions**: Host directories must be accessible to the container user
3. **Read-only volumes**: Use `:ro` suffix for image directories to prevent accidental changes

## Development

### Project Structure

```
omnidupe/
├── main.py                 # Main application entry point
├── src/
│   ├── __init__.py
│   ├── image_scanner.py    # Directory scanning and file detection
│   ├── metadata_extractor.py  # Image metadata and hash extraction
│   ├── duplicate_detector.py  # Multi-stage duplicate detection
│   ├── database.py         # SQLite database operations
│   ├── reporter.py         # Report generation (text, CSV, JSON)
│   └── file_manager.py     # Safe file removal operations
├── requirements.txt        # Python dependencies
├── Dockerfile             # Container configuration
└── README.md              # This file
```

### Running Tests

```bash
# Run with test images
python main.py --input-dir ./test_images --output-dir ./test_output --verbose --dry-run
```

### Contributing

1. Follow Python PEP 8 style guidelines
2. Add appropriate logging for new features
3. Update documentation for API changes
4. Test with various image formats and directory structures

## License

[Add your license information here]

## Support

[Add support contact information here]
