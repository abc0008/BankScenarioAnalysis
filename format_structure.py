import os
import re

def should_include(name, is_dir=False):
    include_patterns = [
        r'\.py$', r'\.js$', r'\.json$', r'\.css$', r'\.html$', r'\.ipynb$',
        r'package(-lock)?\.json$', r'requirements\.txt$', r'\.env$',
        r'start-backend\.js$', r'tailwind\.config\.js$', r'postcss\.config\.js$',
        r'QTX_BankData\.db$', r'GL_FACT\.xlsx$', r'README\.md$'
    ]
    exclude_patterns = [
        r'^\.DS_Store$', r'^node_modules$', r'^build$', r'^\.gitignore$',
        r'\.LICENSE\.txt$', r'\.map$', r'^__pycache__$', r'^\.'
    ]
    
    if is_dir:
        return not any(re.search(pattern, name) for pattern in exclude_patterns)
    else:
        return any(re.search(pattern, name) for pattern in include_patterns) and \
               not any(re.search(pattern, name) for pattern in exclude_patterns)

def generate_structure(start_path='.'):
    output = []

    for root, dirs, files in os.walk(start_path):
        level = root.replace(start_path, '').count(os.sep)
        indent = '  ' * level
        folder_name = os.path.basename(root)
        
        if level == 0 or should_include(folder_name, is_dir=True):
            output.append(f'{indent}├── {folder_name}/')
        
            # Filter and sort directories
            subdirs = [d for d in dirs if should_include(d, is_dir=True)]
            subdirs.sort()
            
            # Filter and sort files
            subfiles = [f for f in files if should_include(f)]
            subfiles.sort()
            
            # Add files
            for f in subfiles:
                output.append(f'{indent}  ├── {f}')
            
            # Modify dirs in-place to affect walk
            dirs[:] = subdirs

    return output

def write_structure(structure, output_file):
    with open(output_file, 'w') as f:
        f.write('\n'.join(structure))
    print(f"Project structure has been saved to '{output_file}'")

# Generate and save the structure
output_file = 'project_structure.txt'
structure = generate_structure()
write_structure(structure, output_file)