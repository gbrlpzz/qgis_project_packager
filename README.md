# QGIS Project Packager

## Overview

**QGIS Project Packager** is a Python script designed to consolidate all files referenced by a QGIS project into a single, portable package. It automatically finds, copies, and organizes all data sources (including vectors, rasters, and zipped layers) used in your project, updates the project file to use relative paths, and creates a clean, zipped folder for easy sharing or archiving.

## Features
- **Finds all referenced files** (even with complex or broken paths)
- **Handles duplicate filenames** by preserving minimal directory structure
- **Copies all sidecar files** for shapefiles
- **Supports .qgs and .qgz projects**
- **Packages everything into a single ZIP**
- **Professional, clean output structure**
- **Technical, concise console output**

## Output Structure
```
YourProject_packaged/
├── YourProject.qgs/.qgz
└── Links/
    ├── Town1/
    │   └── contours.shp
    ├── Town2/
    │   └── contours.shp
    ├── roads.tif
    └── buildings.zip
```

## Requirements
- QGIS (run inside the QGIS Python Console)
- Python 3 (comes with QGIS)
- No external dependencies required

## Usage
1. **Open your QGIS project** (.qgs or .qgz)
2. **Open the QGIS Python Console** (Plugins > Python Console)
3. **Copy and paste the script** (`qgis_project_packager.py`) into the console and run it
4. The script will:
    - Create a folder named `<YourProject>_packaged` in the same directory as your project
    - Copy all referenced files into a `Links/` subdirectory
    - Update the project file to use relative paths
    - Create a ZIP archive of the package

## Troubleshooting
- **Missing files**: The script aggressively searches parent directories, but if files are truly missing, they will be reported in the console output.
- **Duplicate names**: Files with the same name from different folders are kept separate in `Links/<parent_folder>/`.
- **Runs only in QGIS**: The script must be run from the QGIS Python Console (not standalone Python).
- **Orderliness**: the orderliness of the final links folder will be directly proporional to the orderliness of your original file management, just all in the same place.


## Contact
For questions, issues, or contributions, please open an issue or contact the maintainer. 
