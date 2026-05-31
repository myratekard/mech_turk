"""Print the raw VisionAnalysis (incl. name_adjacent_observation) for given images."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.vision_llm import analyze_screenshot  # noqa: E402

for path in sys.argv[1:]:
    with open(path, "rb") as f:
        va = analyze_screenshot(f.read())
    print("=" * 70)
    print(os.path.basename(path))
    print(f"  platform={va.platform} ({va.platform_confidence})")
    print(f"  observation: {va.name_adjacent_observation}")
    print(f"  is_verified={va.is_verified} conf={va.verification_confidence}")
    print(f"  reasoning: {va.reasoning}")
