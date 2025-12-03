import sys
import os
import json
import logging

# Add project root to path
sys.path.append(os.getcwd())

from pbwizard.vision import PinballLayout

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_layout(filename):
    filepath = os.path.join('layouts', filename)
    logger.info(f"Verifying {filepath}...")
    
    try:
        layout = PinballLayout(filepath=filepath)
        logger.info(f"Successfully loaded {layout.name}")
        logger.info(f"  Zones: {len(layout.zones)}")
        logger.info(f"  Bumpers: {len(layout.bumpers)}")
        logger.info(f"  Drop Targets: {len(layout.drop_targets)}")
        logger.info(f"  Rails: {len(layout.rails)}")
        if hasattr(layout, 'upper_flippers'):
            logger.info(f"  Upper Flippers: {len(layout.upper_flippers)}")
        return True
    except Exception as e:
        logger.error(f"Failed to load {filename}: {e}")
        return False

def main():
    layouts = ['classic_fan.json', 'target_practice.json', 'upper_deck.json']
    all_passed = True
    
    for l in layouts:
        if not verify_layout(l):
            all_passed = False
            
    if all_passed:
        print("\nAll layouts verified successfully!")
        sys.exit(0)
    else:
        print("\nSome layouts failed verification.")
        sys.exit(1)

if __name__ == "__main__":
    main()
