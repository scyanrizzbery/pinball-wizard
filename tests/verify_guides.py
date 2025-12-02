import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from pbwizard.physics import PymunkEngine
from pbwizard.vision import PinballLayout

def test_guides():
    print("Initializing Engine...")
    layout = PinballLayout()
    engine = PymunkEngine(layout, 600, 1200)
    
    # Check default
    print(f"Default guide count: {len(engine.guide_shapes)}")
    if len(engine.guide_shapes) != 2:
        print("FAIL: Expected 2 guides")
        sys.exit(1)
        
    # Check thickness
    print(f"Default thickness: {engine.guide_shapes[0].radius}")
    if engine.guide_shapes[0].radius != 25.0:
        print(f"FAIL: Expected thickness 25.0, got {engine.guide_shapes[0].radius}")
        sys.exit(1)
        
    # Update thickness
    print("Updating thickness to 40.0...")
    engine.update_guide_params(thickness=40.0)
    if engine.guide_shapes[0].radius != 40.0:
        print(f"FAIL: Expected thickness 40.0, got {engine.guide_shapes[0].radius}")
        sys.exit(1)
        
    print("SUCCESS: Guide configuration verified.")

if __name__ == "__main__":
    test_guides()
