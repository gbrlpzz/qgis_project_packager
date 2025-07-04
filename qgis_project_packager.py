import os
import shutil
import zipfile
import tempfile
import xml.etree.ElementTree as ET
import glob
from qgis.core import QgsProject

# --- Helper functions ---
def find_file_aggressively(filename, search_roots):
    """Search for a file in multiple root directories recursively"""
    for root in search_roots:
        if os.path.exists(root):
            for path in glob.glob(os.path.join(root, '**', filename), recursive=True):
                if os.path.isfile(path):
                    return path
    return None

def find_zip_aggressively(zip_name, search_roots):
    """Search for a ZIP file in multiple root directories recursively"""
    for root in search_roots:
        if os.path.exists(root):
            for path in glob.glob(os.path.join(root, '**', zip_name), recursive=True):
                if os.path.isfile(path) and path.endswith('.zip'):
                    return path
    return None

def parse_vsizip_path(vsizip_path):
    """Parse /vsizip/ path to get ZIP file and internal path"""
    if not vsizip_path.startswith('/vsizip/'):
        return None, None
    
    # Remove /vsizip/ prefix
    path = vsizip_path[8:]
    
    # Handle |layername= syntax
    if '|' in path:
        path = path.split('|')[0]
    
    # Find .zip in the path
    if '.zip' in path:
        parts = path.split('.zip', 1)
        zip_path = parts[0] + '.zip'
        inner_path = parts[1].lstrip('/') if len(parts) > 1 else ''
        return zip_path, inner_path
    
    return None, None

def resolve_path_aggressively(datasource, project_folder):
    """Try multiple strategies to find a file"""
    # Handle |layername= syntax
    if '|' in datasource:
        datasource = datasource.split('|')[0]
    
    # Direct absolute path
    if os.path.isabs(datasource) and os.path.isfile(datasource):
        return datasource
    
    # Relative to project folder
    resolved = os.path.normpath(os.path.join(project_folder, datasource))
    if os.path.isfile(resolved):
        return resolved
    
    # Search in common parent directories
    search_roots = [
        project_folder,
        os.path.dirname(project_folder),
        os.path.dirname(os.path.dirname(project_folder)),
        os.path.dirname(os.path.dirname(os.path.dirname(project_folder))),
    ]
    
    filename = os.path.basename(datasource)
    found = find_file_aggressively(filename, search_roots)
    if found:
        return found
    
    # Try removing ./ or ../ prefixes and search
    clean_path = datasource.lstrip('./').lstrip('../')
    for root in search_roots:
        candidate = os.path.join(root, clean_path)
        if os.path.isfile(candidate):
            return candidate
    
    return None

def get_unique_output_path(resolved_path, links_folder, copied_paths):
    """Generate a unique output path in the Links directory with minimal structure to avoid naming conflicts"""
    filename = os.path.basename(resolved_path)
    parent_dir = os.path.basename(os.path.dirname(resolved_path))
    
    # Only use parent directory if it's meaningful (not empty, ., .., or common system folders)
    system_folders = {'Documents', 'Desktop', 'Downloads', 'Users', 'home', 'tmp', 'temp', 'Program Files', 'Windows', 'System32'}
    
    if parent_dir and parent_dir not in {'.', '..', ''} and parent_dir not in system_folders:
        # Use parent_dir/filename structure within Links
        output_path = os.path.join(links_folder, parent_dir, filename)
        relative_path = f"Links/{parent_dir}/{filename}"
    else:
        # Just use filename in Links root
        output_path = os.path.join(links_folder, filename)
        relative_path = f"Links/{filename}"
    
    # Handle duplicates by adding numbers
    original_output_path = output_path
    original_relative_path = relative_path
    counter = 1
    
    while output_path in copied_paths:
        name, ext = os.path.splitext(original_output_path)
        output_path = f"{name}_{counter}{ext}"
        
        name_rel, ext_rel = os.path.splitext(original_relative_path)
        relative_path = f"{name_rel}_{counter}{ext_rel}"
        counter += 1
    
    return output_path, relative_path

def copy_shapefile_sidecars(src, output_path):
    """Copy shapefile and all associated files to the specified output path"""
    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    base_src, _ = os.path.splitext(src)
    base_out, _ = os.path.splitext(output_path)
    copied = []
    
    for ext in ['.shp', '.dbf', '.shx', '.prj', '.cpg', '.qix', '.sbn', '.sbx', '.shp.xml', '.fix', '.qpj']:
        src_file = base_src + ext
        if os.path.isfile(src_file):
            out_file = base_out + ext
            shutil.copy2(src_file, out_file)
            copied.append(os.path.basename(out_file))
    
    return copied

# --- Get current project ---
project = QgsProject.instance()
project_path = project.fileName()
if not project_path:
    raise RuntimeError("No QGIS project is currently open.")

print(f"Current project: {project_path}")

project_folder = os.path.dirname(project_path)
project_name, project_ext = os.path.splitext(os.path.basename(project_path))
output_folder = os.path.join(project_folder, f"{project_name}_packaged")
links_folder = os.path.join(output_folder, "Links")

if os.path.exists(output_folder):
    shutil.rmtree(output_folder)
os.makedirs(output_folder)
os.makedirs(links_folder)
print(f"Package directory: {output_folder}")
print(f"Links directory: {links_folder}")

# Search roots for finding missing files
search_roots = [
    project_folder,
    os.path.dirname(project_folder),
    os.path.dirname(os.path.dirname(project_folder)),
    os.path.dirname(os.path.dirname(os.path.dirname(project_folder))),
]

# --- Extract .qgs XML from .qgz if needed ---
if project_ext.lower() == '.qgz':
    print("Processing .qgz file...")
    with zipfile.ZipFile(project_path, 'r') as zipf:
        with zipf.open(f'{project_name}.qgs') as qgsfile:
            xml_data = qgsfile.read()
    qgs_path = os.path.join(tempfile.gettempdir(), f'{project_name}_tmp.qgs')
    with open(qgs_path, 'wb') as f:
        f.write(xml_data)
else:
    qgs_path = project_path

# --- Parse the .qgs XML for all layers ---
print("Processing project layers...")
tree = ET.parse(qgs_path)
root = tree.getroot()
processed_count = 0
skipped_count = 0
copied_paths = set()

for maplayer in root.findall('.//maplayer'):
    provider = maplayer.findtext('provider')
    datasource = maplayer.findtext('datasource')
    name = maplayer.findtext('layername') or 'unnamed'
    
    if not provider or not datasource:
        print(f"Skipping layer '{name}': No datasource")
        skipped_count += 1
        continue
    
    # Handle /vsizip/ paths - copy the entire ZIP file
    if datasource.startswith('/vsizip/'):
        zip_path, inner_path = parse_vsizip_path(datasource)
        if zip_path:
            resolved_zip = resolve_path_aggressively(zip_path, project_folder)
            if resolved_zip:
                output_path, relative_path = get_unique_output_path(resolved_zip, links_folder, copied_paths)
                
                output_dir = os.path.dirname(output_path)
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                
                if output_path not in copied_paths:
                    shutil.copy2(resolved_zip, output_path)
                    copied_paths.add(output_path)
                    print(f"Copied: {relative_path}")
                
                # Update XML to point to the copied ZIP
                new_datasource = f"/vsizip/./{relative_path}"
                if inner_path:
                    new_datasource += f"/{inner_path}"
                if '|' in datasource:
                    new_datasource += '|' + datasource.split('|', 1)[1]
                
                datasource_elem = maplayer.find('datasource')
                if datasource_elem is not None:
                    datasource_elem.text = new_datasource
                processed_count += 1
            else:
                print(f"ZIP file not found: {zip_path}")
                skipped_count += 1
        else:
            print(f"Invalid vsizip path: {datasource}")
            skipped_count += 1
        continue
    
    # Handle regular file paths
    resolved = resolve_path_aggressively(datasource, project_folder)
    if resolved:
        ext = os.path.splitext(resolved)[1].lower()
        output_path, relative_path = get_unique_output_path(resolved, links_folder, copied_paths)
        
        if ext == '.shp':
            files = copy_shapefile_sidecars(resolved, output_path)
            if files:
                datasource_elem = maplayer.find('datasource')
                if datasource_elem is not None:
                    new_path = relative_path
                    if '|' in datasource:
                        new_path += '|' + datasource.split('|', 1)[1]
                    datasource_elem.text = new_path
                processed_count += 1
                copied_paths.add(output_path)
                print(f"Copied shapefile: {relative_path}")
            else:
                print(f"Shapefile components missing: {resolved}")
                skipped_count += 1
        else:
            if output_path not in copied_paths:
                output_dir = os.path.dirname(output_path)
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                
                shutil.copy2(resolved, output_path)
                copied_paths.add(output_path)
                print(f"Copied: {relative_path}")
            
            datasource_elem = maplayer.find('datasource')
            if datasource_elem is not None:
                new_path = relative_path
                if '|' in datasource:
                    new_path += '|' + datasource.split('|', 1)[1]
                datasource_elem.text = new_path
            processed_count += 1
    else:
        print(f"File not found: {datasource}")
        skipped_count += 1

print(f"Processed: {processed_count} layers | Skipped: {skipped_count} layers")

# --- Save updated .qgs ---
updated_qgs_path = os.path.join(output_folder, f'{project_name}.qgs')
tree.write(updated_qgs_path, encoding='utf-8', xml_declaration=True)
print(f"Project file saved: {os.path.basename(updated_qgs_path)}")

# --- If original was .qgz, repackage ---
if project_ext.lower() == '.qgz':
    updated_qgz_path = os.path.join(output_folder, f'{project_name}.qgz')
    with zipfile.ZipFile(updated_qgz_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(updated_qgs_path, os.path.basename(updated_qgs_path))
    print(f"Project file saved: {os.path.basename(updated_qgz_path)}")

# --- Zip the folder ---
zip_path = output_folder + '.zip'
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for rootdir, dirs, files in os.walk(output_folder):
        for file in files:
            abs_path = os.path.join(rootdir, file)
            rel_path = os.path.relpath(abs_path, output_folder)
            zipf.write(abs_path, rel_path)

print(f"Package created: {os.path.basename(zip_path)}")
print(f"Output directory: {output_folder}") 