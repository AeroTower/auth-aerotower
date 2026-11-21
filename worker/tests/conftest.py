import sys
from pathlib import Path

# worker/ no caminho de import: `import consumer`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
