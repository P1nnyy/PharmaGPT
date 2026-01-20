import os

# Configuration
SOURCE_ROOT = "/Users/pranavgupta/Desktop/untitled folder/Invoice Extractor"
OUTPUT_FILE = "/Users/pranavgupta/Desktop/codebase.txt"

# Extensions to include
ALLOWED_EXTENSIONS = {
    '.py', '.js', '.jsx', '.ts', '.tsx', '.css', '.html', '.json'
}

# Directories to skip entirely
SKIP_DIRS = {
    'node_modules', '.venv', '.git', '__pycache__', 'dist', 'build', 
    'uploads', 'static', 'data', 'logs', '.idea', '.vscode', '.pytest_cache',
    'coverage', '.next'
}

# Specific files to skip
SKIP_FILES = {
    'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml', 'poetry.lock', 
    'Pipfile.lock', '.DS_Store', '.env', '.env.local', '.env.development',
    '.env.production', 'backend.log', 'cloudflared.log'
}

# Specific files to ALWAYS include (even if extension matches above, though usually consistent)
INCLUDE_FILES = {
    'Dockerfile', 'docker-compose.yml', 'requirements.txt', 'README.md'
}

def is_code_file(filename):
    if filename in SKIP_FILES:
        return False
    if filename in INCLUDE_FILES:
        return True
    _, ext = os.path.splitext(filename)
    return ext in ALLOWED_EXTENSIONS

def main():
    print(f"Starting export from {SOURCE_ROOT} to {OUTPUT_FILE}...")
    
    count = 0
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as outfile:
        # Header
        outfile.write(f"Codebase Export\n")
        outfile.write(f"Source: {SOURCE_ROOT}\n")
        outfile.write(f"================================================================\n\n")

        for root, dirs, files in os.walk(SOURCE_ROOT):
            # Modify dirs in-place to skip strict directories
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('.')]
            
            for file in files:
                if is_code_file(file):
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, SOURCE_ROOT)
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as infile:
                            content = infile.read()
                            
                        outfile.write(f"File: {rel_path}\n")
                        outfile.write("-" * (6 + len(rel_path)) + "\n")
                        outfile.write(content)
                        outfile.write("\n\n" + "="*80 + "\n\n")
                        count += 1
                        # print(f"Exported: {rel_path}")
                    except Exception as e:
                        print(f"Failed to read {file_path}: {e}")

    print(f"Export complete! {count} files written to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
