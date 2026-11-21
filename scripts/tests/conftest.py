import sys
from pathlib import Path

# scripts/ no caminho de import: `import provisionar_torre`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
