import os
import tomllib
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env')
DEFAULTS = tomllib.loads((ROOT / 'config/app.toml').read_text())
APP_NAME = DEFAULTS['name']
DATA = Path(os.getenv('ATLAS_DATA_DIR', str(ROOT / 'data'))).resolve()

def setting(key):
    value = int(os.getenv('ATLAS_' + key.upper(), DEFAULTS[key]))
    if value <= 0:
        raise ValueError(f'{key} must be positive')
    return value

for _key in DEFAULTS:
    if _key != 'name':
        setting(_key)

def directories():
    for folder in ('uploads', 'audit', 'chroma'):
        (DATA / folder).mkdir(parents=True, exist_ok=True)
