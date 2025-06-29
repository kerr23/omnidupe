# OmniDupe - Duplicate Image Finder

A Python application that recursively searches directories for duplicate and visually similar images using metadata analysis, file content hashing, and perceptual hashing.

## Features

- **Multi-stage Duplicate Detection**:
  - Primary: Timestamp metadata matching (EXIF DateTimeOriginal, CreateDate)
  - Secondary: File content hash matching (SHA-256)
  - Tertiary: Perceptual similarity using multiple hash algorithms (pHash, aHash, dHash, wHash)

- **Mode-based Operation**:
  - **Detect mode**: Scans for duplicates, stores results in persistent database, marks files for removal
  - **Remove mode**: Reads database and removes images marked for deletion
  - **Protect mode**: Marks specific images as protected from deletion

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
  - Image protection system to prevent accidental deletion
  - Persistent database tracks all operations

- **Performance Optimized**:
  - Parallel processing for I/O-bound operations
  - SQLite database for efficient metadata storage and querying
  - Configurable worker thread limits
  - Skips system directories (@eaDir for Synology NAS)

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

OmniDupe operates in three distinct modes:

### Mode 1: Detect Duplicates

Scan for duplicates and store results in the database:

```bash
python main.py detect --input-dir /path/to/images --output-dir /path/to/results
```

Advanced detection with custom settings:
```bash
python main.py detect \
  --input-dir /path/to/images \
  --output-dir /path/to/results \
  --similarity-threshold 5 \
  --report-format csv \
  --max-workers 8 \
  --verbose
```

### Mode 2: Remove Duplicates

Remove images that were marked for deletion during detection:

```bash
python main.py remove --output-dir /path/to/results
```

With dry-run to see what would be deleted:
```bash
python main.py remove --output-dir /path/to/results --dry-run --verbose
```

### Mode 3: Protect Images

Mark specific images as protected from deletion:

```bash
python main.py protect --output-dir /path/to/results --file-path /path/to/image.jpg
```

### Complete Workflow Example

```bash
# Step 1: Detect duplicates and create database
python main.py detect -i /photos -o /results --verbose

# Step 2: Protect important images (optional)
python main.py protect -o /results --file-path /photos/family/wedding.jpg
python main.py protect -o /results --file-path /photos/vacation/sunset.jpg

# Step 3: Preview what will be deleted
python main.py remove -o /results --dry-run

# Step 4: Actually remove the duplicates
python main.py remove -o /results
```

### Docker Usage

Detection mode:
```bash
docker run --rm \
  -v /path/to/images:/images:ro \
  -v /path/to/output:/data \
  omnidupe \
  detect --input-dir /images --output-dir /data --verbose
```

Removal mode:
```bash
docker run --rm \
  -v /path/to/images:/images \
  -v /path/to/output:/data \
  omnidupe \
  remove --output-dir /data --dry-run
```

Protect mode:
```bash
docker run --rm \
  -v /path/to/images:/images \
  -v /path/to/output:/data \
  omnidupe \
  protect --output-dir /data --file-path /images/important.jpg
```

## Command Line Options

### Detect Mode
| Option | Description | Default |
|--------|-------------|---------|
| `--input-dir`, `-i` | Directory to scan for images | Required |
| `--output-dir`, `-o` | Directory to store reports and database | `./output` |
| `--similarity-threshold` | Hamming distance threshold for perceptual similarity | `5` |
| `--report-format` | Output report format (`text`, `csv`, `json`) | `text` |
| `--max-workers` | Maximum number of worker threads | `4` |
| `--verbose`, `-v` | Enable verbose logging | `False` |

### Remove Mode
| Option | Description | Default |
|--------|-------------|---------|
| `--output-dir`, `-o` | Directory containing the database | `./output` |
| `--dry-run` | Show what would be deleted without actually deleting | `False` |
| `--verbose`, `-v` | Enable verbose logging | `False` |

### Protect Mode
| Option | Description | Default |
|--------|-------------|---------|
| `--output-dir`, `-o` | Directory containing the database | `./output` |
| `--file-path` | Path to image file to protect | Required |
| `--verbose`, `-v` | Enable verbose logging | `False` |

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

- **⚡ Persistent Database (HIGHLY RECOMMENDED)**: Use `--persistent-db` to cache metadata between runs:
  - **First run**: Processes all images and saves metadata to `omnidupe.db`
  - **Subsequent runs**: Only processes new/modified images (dramatically faster)
  - **Ideal for**: Large image collections (>1000 images) or regular scanning
  - **Example**: First scan takes 30 minutes, subsequent scans take 2-3 minutes
- **Parallel processing**: Configurable worker threads for I/O operations
- **Database indexing**: Optimized database queries with proper indexing
- **Memory efficiency**: Processes images in streams to minimize memory usage
- **Incremental processing**: Database persistence allows resuming interrupted operations
- **Batch operations**: Groups database operations for better performance

### Performance Tips for Large Collections

1. **Always use `--persistent-db`** for collections with hundreds or thousands of images
2. **First run setup**:
   ```bash
   # Initial scan - will take time but builds the database
   python main.py --input-dir /large/photo/collection --output-dir ./results --persistent-db --verbose
   ```
3. **Subsequent runs** (much faster):
   ```bash
   # Only processes new/changed images
   python main.py --input-dir /large/photo/collection --output-dir ./results --persistent-db
   ```
4. **Adjust workers** based on your system: `--max-workers 8` for powerful systems
5. **Monitor progress** with `--verbose` flag to see processing status

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
