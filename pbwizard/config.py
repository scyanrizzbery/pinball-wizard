import hashlib
import json
from dataclasses import dataclass, asdict


@dataclass
class PhysicsConfig:
    """Configuration schema for pinball physics parameters."""
    
    # Global Physics
    gravity_magnitude: float = 9000.0
    table_tilt: float = 8.5  # degrees
    friction: float = 0.01
    restitution: float = 0.5
    
    # Ball
    ball_mass: float = 1.0
    ball_radius: float = 10.0 # Pixel radius, usually derived but good to catch
    
    # Flippers
    flipper_speed: float = 20.0  # Updated from 30.0 to match config.json
    flipper_resting_angle: float = -36.0  # Updated from 30.0 to match config.json (note sign change)
    flipper_stroke_angle: float = 42.0  # Updated from -30.0 to match config.json
    flipper_length: float = 0.23  # Updated from 0.12 to match config.json
    flipper_width: float = 0.05
    flipper_spacing: float = 0.0 # Additional gap between flippers (from center-line)
    flipper_tip_width: float = 0.025
    flipper_elasticity: float = 0.5
    flipper_friction: float = 0.01
    
    # Plunger
    launch_angle: float = 0.0
    plunger_release_speed: float = 1500.0  # Updated from 1800.0 to match config.json
    
    # Bumpers
    bumper_force: float = 800.0
    bumper_respawn_time: float = 10.0
    
    # Drop Targets
    drop_target_cooldown: float = 2.0
    
    # Tilt / Nudge
    nudge_cost: float = 2.4  # Updated from 0.1 to match config.json
    tilt_decay: float = 0.06  # Updated from 0.005 to match config.json
    tilt_threshold: float = 10.0  # Updated from 1.0 to match config.json
    
    # Combo System
    combo_window: float = 3.0
    multiplier_max: float = 5.0
    base_combo_bonus: int = 50
    combo_multiplier_enabled: bool = True
    
    # Auto-Play
    auto_plunge_enabled: bool = True
    
    # Rails / Guides (Visual/Physics alignment)
    rail_x_offset: float = 0.0
    rail_y_offset: float = 0.0
    guide_thickness: float = 10.0
    guide_length_scale: float = 1.0
    guide_angle_offset: float = 0.0

    def to_dict(self):
        return asdict(self)

    def get_hash(self):
        """Generate a deterministic hash of the configuration."""
        data = self.to_dict()
        # Sort keys to ensure consistent JSON
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode('utf-8')).hexdigest()[:16]

    @classmethod
    def from_dict(cls, data: dict):
        # Filter unknown keys to prevent init errors
        valid_keys = cls.__dataclass_fields__.keys()
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        # Handle type conversion if necessary (e.g. strings to floats from JSON)
        # relying on runtime usage or pydantic would be better but this is stdlib
        return cls(**filtered_data)
        
    def update(self, data: dict):
        """Update existing config from dictionary."""
        valid_keys = self.__dataclass_fields__.keys()
        for k, v in data.items():
            if k in valid_keys and v is not None:
                # Basic type casting can be added here if needed
                try:
                    target_type = self.__annotations__[k]
                    if target_type == bool and isinstance(v, str):
                        v = v.lower() == 'true'
                    elif target_type in (int, float) and isinstance(v, str):
                        v = target_type(v)
                    
                    setattr(self, k, v)
                except (ValueError, TypeError):
                    pass # Keep original if cast fails
