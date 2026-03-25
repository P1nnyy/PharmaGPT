print('Starting Debug Import')
import sys; os = __import__('os'); sys.path.append(os.getcwd())
print('Importing server...')
try:
    from src.api.server import app
    print('Import Success')
except Exception as e:
    print(f'Import Failed: {e}')
