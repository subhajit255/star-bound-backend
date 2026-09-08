import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from detection.pipeline import detect_image

image_path = Path(sys.argv[1])
result = detect_image(image_path)
print(json.dumps(result.as_dict(), indent=2))
