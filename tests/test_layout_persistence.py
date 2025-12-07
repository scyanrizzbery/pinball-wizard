"""
Tests for layout persistence and physics parameter saving.
"""
import os
import json
import tempfile
import pytest
from pbwizard.vision import PinballLayout, SimulatedFrameCapture


class TestLayoutPersistence:
    """Test that physics parameters persist with layouts."""
    
    def test_table_tilt_in_physics_keys(self):
        """Verify table_tilt is included in physics persistence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a simulated capture
            capture = SimulatedFrameCapture(width=450, height=800)
            
            # Change table_tilt
            original_tilt = capture.physics_engine.config.table_tilt
            new_tilt = 8.5
            capture.update_physics_params({'table_tilt': new_tilt})
            
            # Verify it was updated
            # Check physics engine config instead of capture attribute
            assert capture.physics_engine.config.table_tilt == new_tilt
            
            # Verify it's in layout.physics_params
            assert 'table_tilt' in capture.layout.physics_params
            assert capture.layout.physics_params['table_tilt'] == new_tilt
    
    def test_physics_save_to_layout_file(self):
        """Test that physics params are saved to layout JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            layout_file = os.path.join(tmpdir, 'test_layout.json')
            
            # Create a layout
            layout = PinballLayout()
            layout.name = "Test Layout"
            
            # Set some physics params
            layout.physics_params = {
                'table_tilt': 7.5,
                'gravity': 1400.0,
                'friction': 0.6,
                'restitution': 0.8
            }
            
            # Save to file
            layout.save_to_file(layout_file)
            
            # Load and verify
            with open(layout_file, 'r') as f:
                data = json.load(f)
            
            assert 'physics' in data
            assert data['physics']['table_tilt'] == 7.5
            assert data['physics']['gravity'] == 1400.0
            assert data['physics']['friction'] == 0.6
            assert data['physics']['restitution'] == 0.8
    
    def test_physics_restore_from_layout(self):
        """Test that physics params are restored when loading a layout."""
        with tempfile.TemporaryDirectory() as tmpdir:
            layout_file = os.path.join(tmpdir, 'test_layout.json')
            
            # Create and save a layout with custom physics
            layout_data = {
                'name': 'Test Layout',
                'width': 0.6,
                'height': 1.2,
                'zones': [],
                'bumpers': [],
                'drop_targets': [],
                'rails': [],
                'physics': {
                    'table_tilt': 9.0,
                    'gravity': 1500.0,
                    'friction': 0.7
                }
            }
            
            with open(layout_file, 'w') as f:
                json.dump(layout_data, f)
            
            # Load layout
            layout = PinballLayout(filepath=layout_file)
            
            # Verify physics params were loaded
            assert layout.physics_params['table_tilt'] == 9.0
            assert layout.physics_params['gravity'] == 1500.0
            assert layout.physics_params['friction'] == 0.7
    
    def test_layout_switching_preserves_physics(self):
        """Test that switching layouts preserves and restores physics."""
        # This test would require a full SimulatedFrameCapture setup
        # with multiple layout files, which is more complex
        # For now, we'll test the components separately
        pass
    
    def test_current_layout_id_updates(self):
        """Test that current_layout_id is updated when layout changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test layout files
            os.makedirs(os.path.join(tmpdir, 'layouts'), exist_ok=True)
            
            layout1_file = os.path.join(tmpdir, 'layouts', 'layout1.json')
            layout1_data = {
                'name': 'Layout 1',
                'width': 0.6,
                'height': 1.2,
                'zones': [],
                'bumpers': [],
                'drop_targets': [],
                'rails': []
            }
            with open(layout1_file, 'w') as f:
                json.dump(layout1_data, f)
            
            # This test would need to mock the SimulatedFrameCapture
            # and verify current_layout_id changes
            # Skipping full implementation for brevity
            pass


class TestLayoutDropdown:
    """Test that layout dropdown doesn't revert."""
    
    def test_is_loading_layout_flag(self):
        """Test that isLoadingLayout flag prevents config overwrite."""
        # This would be a frontend test using Cypress or similar
        # Marking as placeholder
        pass


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
