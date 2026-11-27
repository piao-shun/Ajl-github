import sys
from pathlib import Path

# 让 tests 目录里的用例能直接 import app 包
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))