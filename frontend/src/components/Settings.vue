<template>
  <div id="physics-controls">
    <!-- Top Controls (Model, Layout, View) -->
    <div class="top-controls">
      <div class="control-group">
        <div style="flex: 1;">
          <div class="label">Model</div>
          <select :value="selectedModel" @change="$emit('update:selectedModel', $event.target.value); $emit('load-model')"
            class="select-input" :disabled="stats.is_training">
            <option v-for="model in models" :key="model.filename" :value="model.filename">
              {{ model.filename }} ({{ model.mod_time || model.hash }})
            </option>
          </select>
        </div>
      </div>
      <div class="control-group">
        <div style="flex: 1;">
          <div class="label">Table Layout</div>
          <div style="display: flex; gap: 5px;">
            <select :value="selectedLayout" @change="$emit('change-layout', $event.target.value)" class="select-input"
              :disabled="stats.is_training" style="flex: 1;">
              <option v-for="layout in layouts" :key="layout.id" :value="layout.id">
                {{ layout.name }}
              </option>
            </select>
            <button @click="saveLayout" class="control-btn" title="Save Layout" style="padding: 0 10px; font-size: 1.2em;" :disabled="stats.is_training">
              💾
            </button>
            <button @click="saveLayoutAs" class="control-btn" title="Save Layout As..." style="padding: 0 10px; font-size: 1.2em;" :disabled="stats.is_training">
              ➕
            </button>
            <button @click="saveLayoutSettings" class="control-btn" title="Save Settings to Layout" style="padding: 0 10px; font-size: 1.2em;" :disabled="stats.is_training">
              ⚙️💾
            </button>
          </div>
        </div>
      </div>
      <div class="control-group">
        <div style="flex: 1;">
          <div class="label">View</div>
          <div style="display: flex; gap: 5px;">
            <select :value="selectedPreset" @change="$emit('update:selectedPreset', $event.target.value); $emit('apply-preset', $event.target.value)"
              class="select-input" :disabled="stats.is_training" style="flex: 1;">
              <option value="" disabled>Select Camera Preset</option>
              <option v-for="(preset, name) in cameraPresets" :key="name" :value="name">{{ name }}</option>
            </select>
            <button @click="savePreset" class="control-btn" title="Save View" style="padding: 0 10px; font-size: 1.2em;" :disabled="stats.is_training || !selectedPreset">
              💾
            </button>
            <button @click="savePresetAs" class="control-btn" title="Save View As..." style="padding: 0 10px; font-size: 1.2em;" :disabled="stats.is_training">
              ➕
            </button>
          </div>
        </div>
      </div>
      <div class="control-group">
        <div style="flex: 1;">
          <div class="label">AI Difficulty</div>
          <select :value="selectedDifficulty" @change="$emit('update-difficulty', $event.target.value)"
            class="select-input" :disabled="stats.is_training">
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </select>
        </div>
      </div>
    </div>

    <div class="tabs">
      <button class="tab" :class="{ active: activeTab === 'settings' }" @click="activeTab = 'settings'">Settings</button>
      <button class="tab" :class="{ active: activeTab === 'training' }" @click="activeTab = 'training'">Training</button>
    </div>

    <!-- Settings Tab -->
    <div v-show="activeTab === 'settings'" class="tab-content">
      <!-- Ball Physics Group -->
      <div class="group-header" @click="toggleGroup('ball')">
        <span>Ball Physics</span>
        <span class="arrow" :class="{ rotated: groupsExpanded.ball }">▼</span>
      </div>
      <div v-if="groupsExpanded.ball" class="group-content">
        <div class="slider-container">
          <div class="slider-label">
            <span>Table Tilt</span>
            <span>{{ formatNumber(physics.table_tilt, 1) }}°</span>
          </div>
          <input type="range" min="-180.0" max="180.0" step="5" v-model.number="physics.table_tilt">
        </div>
        <div class="slider-container">
          <div class="slider-label">
            <span>Friction</span>
            <span>{{ formatNumber(physics.friction, 3) }}</span>
          </div>
          <input type="range" min="0.01" max="2.000" step="0.01" v-model.number="physics.friction">
        </div>
        <div class="slider-container">
          <div class="slider-label">
            <span>Restitution (Bounce)</span>
            <span>{{ formatNumber(physics.restitution, 2) }}</span>
          </div>
          <input type="range" min="0.1" max="2.0" step="0.01" v-model.number="physics.restitution"
            :disabled="stats.is_training">
        </div>
        <div class="slider-container">
          <div class="slider-label">
            <span>Plunger Force</span>
            <span>{{ formatNumber(physics.plunger_release_speed, 0) }}</span>
          </div>
          <input type="range" min="0" max="4000" step="100" v-model.number="physics.plunger_release_speed"
            :disabled="stats.is_training">
        </div>
        <div class="slider-container">
          <div class="slider-label">
            <span>Launch Angle</span>
            <span>{{ formatNumber(physics.launch_angle, 1) }}°</span>
          </div>
          <input type="range" min="-90" max="90" step="1" v-model.number="physics.launch_angle"
            :disabled="stats.is_training">
        </div>
        <div class="slider-container">
          <div class="slider-label">
            <span>Ball Weight</span>
            <span>{{ formatNumber(physics.ball_mass, 2) }}</span>
          </div>
          <input type="range" min="0.1" max="5.0" step="0.1" v-model.number="physics.ball_mass"
            :disabled="stats.is_training">
        </div>
      </div>

      <!-- Flipper Group -->
        <div class="group-header" @click="toggleGroup('flipper')">
            <span>Flipper Mechanics</span>
            <span class="arrow" :class="{ rotated: groupsExpanded.flipper }">▼</span>
        </div>
        <div v-if="groupsExpanded.flipper" class="group-content">
            <div class="control-group checkbox-group">
                <div class="checkbox-label">Show Flipper Zones</div>
                <input
                    id="zones-toggle"
                    type="checkbox"
                    v-model="showZones"
                    @change="updateShowZones"
                >
            </div>
            <div class="slider-container">
                <div class="slider-label">
                    <span>Speed</span>
                    <span>{{ formatNumber(physics.flipper_speed, 1) }}</span>
                </div>
                <input type="range" min="0" max="60" step="0.1" v-model.number="physics.flipper_speed"
                       :disabled="stats.is_training">
        </div>
        <div class="slider-container">
          <div class="slider-label">
            <span>Resting Angle</span>
            <span>{{ physics.flipper_resting_angle }}</span>
          </div>
          <input type="range" v-model.number="physics.flipper_resting_angle" min="-60" max="0" step="1"
            :disabled="stats.is_training">
        </div>
        <div class="slider-container">
          <div class="slider-label">
            <span>Stroke Angle</span>
            <span>{{ physics.flipper_stroke_angle }}</span>
          </div>
          <input type="range" v-model.number="physics.flipper_stroke_angle" min="10" max="90" step="1"
            :disabled="stats.is_training">
        </div>
        <div class="slider-container">
          <div class="slider-label">
            <span>Length</span>
            <span>{{ formatNumber(physics.flipper_length, 2) }}</span>
          </div>
          <input type="range" min="0.1" max="0.3" step="0.01" v-model.number="physics.flipper_length"
            :disabled="stats.is_training">
        </div>
        <div class="slider-container">
          <div class="slider-label">
            <span>Head Width</span>
            <span>{{ formatNumber(physics.flipper_width, 3) }}</span>
          </div>
          <input type="range" min="0.01" max="0.05" step="0.001" v-model.number="physics.flipper_width"
            :disabled="stats.is_training">
        </div>
        <div class="slider-container">
          <div class="slider-label">
            <span>Tip Width</span>
            <span>{{ formatNumber(physics.flipper_tip_width, 3) }}</span>
          </div>
          <input type="range" min="0.001" max="0.05" step="0.001" v-model.number="physics.flipper_tip_width"
            :disabled="stats.is_training">
        </div>
        <div class="slider-container">
          <div class="slider-label">
            <span>Rubber Bounce</span>
            <span>{{ formatNumber(physics.flipper_elasticity, 2) }}</span>
          </div>
          <input type="range" min="0.0" max="1.5" step="0.05" v-model.number="physics.flipper_elasticity"
            :disabled="stats.is_training">
        </div>
        
        <div style="margin-bottom: 10px; margin-top: 15px; color: #aaa; font-size: 0.8em; border-top: 1px dashed #333; padding-top: 10px;">Left Flipper Position</div>
        <div class="slider-container">
          <div class="slider-label">
            <span>Pos X</span>
            <span>{{ formatNumber(physics.left_flipper_pos_x, 2) }}</span>
          </div>
          <input type="range" min="0.0" max="0.5" step="0.01" v-model.number="physics.left_flipper_pos_x"
            :disabled="stats.is_training">
        </div>
        <div class="slider-container">
          <div class="slider-label">
            <span>Pos Y</span>
            <span>{{ formatNumber(physics.left_flipper_pos_y, 2) }}</span>
          </div>
          <input type="range" min="0.5" max="1.0" step="0.01" v-model.number="physics.left_flipper_pos_y"
            :disabled="stats.is_training">
        </div>

        <div style="margin-bottom: 10px; margin-top: 10px; color: #aaa; font-size: 0.8em;">Right Flipper Position</div>
        <div class="slider-container">
          <div class="slider-label">
            <span>Pos X</span>
            <span>{{ formatNumber(physics.right_flipper_pos_x, 2) }}</span>
          </div>
          <input type="range" min="0.5" max="1.0" step="0.01" v-model.number="physics.right_flipper_pos_x"
            :disabled="stats.is_training">
        </div>
        <div class="slider-container">
          <div class="slider-label">
            <span>Pos Y</span>
            <span>{{ formatNumber(physics.right_flipper_pos_y, 2) }}</span>
          </div>
          <input type="range" min="0.5" max="1.0" step="0.01" v-model.number="physics.right_flipper_pos_y"
            :disabled="stats.is_training">
        </div>

        <div style="margin-bottom: 10px; margin-top: 15px; color: #aaa; font-size: 0.8em; border-top: 1px dashed #333; padding-top: 10px;">Plunger Settings</div>
        <div class="slider-container">
          <div class="slider-label">
            <span>Launch Angle</span>
            <span>{{ physics.launch_angle }}°</span>
          </div>
          <input type="range" min="-45" max="45" step="1" v-model.number="physics.launch_angle"
            :disabled="stats.is_training">
        </div>
        <div class="slider-container">
          <div class="slider-label">
            <span>Release Speed</span>
            <span>{{ physics.plunger_release_speed }}</span>
          </div>
          <input type="range" min="500" max="3000" step="100" v-model.number="physics.plunger_release_speed"
            :disabled="stats.is_training">
        </div>
        
        <div class="slider-container" style="justify-content: space-between; align-items: center; border-top: 1px dashed #333; padding-top: 10px; margin-top: 10px;">
          <div class="slider-label">
            <span style="color: #FFD700; font-weight: bold;">GOD MODE 😇</span>
          </div>
          <input type="checkbox" :checked="physics.god_mode" 
            @change="updatePhysics('god_mode', $event.target.checked)"
            :disabled="stats.is_training">
        </div>



      </div>
      


      <!-- Rail Group -->
      <div class="group-header" @click="toggleGroup('rails')">
        <span>Rail Settings</span>
        <span class="arrow" :class="{ rotated: groupsExpanded.rails }">▼</span>
      </div>
      <div v-if="groupsExpanded.rails" class="group-content">
        <div class="slider-container" style="justify-content: space-between; align-items: center;">
          <div class="slider-label">
            <span>Show Rail Debug (Yellow Lines)</span>
          </div>
          <input type="checkbox" :checked="physics.show_rail_debug" 
            @change="updatePhysics('show_rail_debug', $event.target.checked)">
        </div>

          <div style="margin-bottom: 5px; margin-top: 15px; color: #999; font-size: 0.85em; border-top: 1px dashed #333; padding-top: 10px;">Rail Translation</div>
          <div class="slider-container">
              <div class="slider-label">
                  <span>X Offset (Left/Right)</span>
                  <span>{{ formatNumber(physics.rail_x_offset, 2) }}</span>
              </div>
              <input type="range" min="-1.0" max="1.0" step="0.01" v-model.number="physics.rail_x_offset"
                     :disabled="stats.is_training">
          </div>
          <div class="slider-container">
              <div class="slider-label">
                  <span>Y Offset (Up/Down)</span>
                  <span>{{ formatNumber(physics.rail_y_offset, 2) }}</span>
              </div>
              <input type="range" min="-1.0" max="1.0" step="0.01" v-model.number="physics.rail_y_offset"
                     :disabled="stats.is_training">
          </div>


          <div style="margin-bottom: 5px; color: #999; font-size: 0.85em;">Left Rail Position</div>
        <div class="slider-container">
          <div class="slider-label">
            <span>Start X</span>
            <span>{{ formatNumber(physics.rail_left_p1_x, 2) }}</span>
          </div>
          <input type="range" min="0.0" max="0.5" step="0.01" v-model.number="physics.rail_left_p1_x"
            :disabled="stats.is_training">
        </div>
        <div class="slider-container">
          <div class="slider-label">
            <span>Start Y</span>
            <span>{{ formatNumber(physics.rail_left_p1_y, 2) }}</span>
          </div>
          <input type="range" min="0.0" max="1.0" step="0.01" v-model.number="physics.rail_left_p1_y"
            :disabled="stats.is_training">
        </div>
        <div class="slider-container">
          <div class="slider-label">
            <span>End X</span>
            <span>{{ formatNumber(physics.rail_left_p2_x, 2) }}</span>
          </div>
          <input type="range" min="0.0" max="0.5" step="0.01" v-model.number="physics.rail_left_p2_x"
            :disabled="stats.is_training">
        </div>
        <div class="slider-container">
          <div class="slider-label">
            <span>End Y</span>
            <span>{{ formatNumber(physics.rail_left_p2_y, 2) }}</span>
          </div>
          <input type="range" min="0.0" max="1.0" step="0.01" v-model.number="physics.rail_left_p2_y"
            :disabled="stats.is_training">
        </div>
        
        <div style="margin-bottom: 5px; margin-top: 10px; color: #999; font-size: 0.85em;">Right Rail Position</div>
        <div class="slider-container">
          <div class="slider-label">
            <span>Start X</span>
            <span>{{ formatNumber(physics.rail_right_p1_x, 2) }}</span>
          </div>
          <input type="range" min="0.5" max="1.0" step="0.01" v-model.number="physics.rail_right_p1_x"
            :disabled="stats.is_training">
        </div>
        <div class="slider-container">
          <div class="slider-label">
            <span>Start Y</span>
            <span>{{ formatNumber(physics.rail_right_p1_y, 2) }}</span>
          </div>
          <input type="range" min="0.0" max="1.0" step="0.01" v-model.number="physics.rail_right_p1_y"
            :disabled="stats.is_training">
        </div>
        <div class="slider-container">
          <div class="slider-label">
            <span>End X</span>
            <span>{{ formatNumber(physics.rail_right_p2_x, 2) }}</span>
          </div>
          <input type="range" min="0.5" max="1.0" step="0.01" v-model.number="physics.rail_right_p2_x"
            :disabled="stats.is_training">
        </div>
        <div class="slider-container">
          <div class="slider-label">
            <span>End Y</span>
            <span>{{ formatNumber(physics.rail_right_p2_y, 2) }}</span>
          </div>
          <input type="range" min="0.0" max="1.0" step="0.01" v-model.number="physics.rail_right_p2_y"
            :disabled="stats.is_training">
        </div>
        
        <div style="margin-bottom: 5px; margin-top: 15px; color: #999; font-size: 0.85em; border-top: 1px dashed #333; padding-top: 10px;">Rail Transformations</div>
        <div class="slider-container">
          <div class="slider-label">
            <span>Thickness</span>
            <span>{{ formatNumber(physics.guide_thickness, 1) }}</span>
          </div>
          <input type="range" min="5.0" max="50.0" step="1.0" v-model.number="physics.guide_thickness"
            :disabled="stats.is_training">
        </div>
        <div class="slider-container">
          <div class="slider-label">
            <span>Length Scale</span>
            <span>{{ formatNumber(physics.guide_length_scale, 2) }}</span>
          </div>
          <input type="range" min="0.5" max="1.5" step="0.05" v-model.number="physics.guide_length_scale"
            :disabled="stats.is_training">
        </div>
        <div class="slider-container">
          <div class="slider-label">
            <span>Angle Offset</span>
            <span>{{ formatNumber(physics.guide_angle_offset, 1) }}°</span>
          </div>
          <input type="range" min="-45.0" max="45.0" step="1.0" v-model.number="physics.guide_angle_offset"
            :disabled="stats.is_training">
        </div>
      </div>

      <!-- Combo Group -->
      <div class="group-header" @click="toggleGroup('combo')">
        <span>Combo Settings</span>
        <span class="arrow" :class="{ rotated: groupsExpanded.combo }">▼</span>
      </div>
      <div v-if="groupsExpanded.combo" class="group-content">
        <div class="slider-container" style="justify-content: space-between; align-items: center;">
          <div class="slider-label">
            <span>Enable Multiplier</span>
          </div>
          <input type="checkbox" :checked="physics.combo_multiplier_enabled" 
            @change="updatePhysics('combo_multiplier_enabled', $event.target.checked)">
        </div>
        <div class="slider-container">
          <div class="slider-label">
            <span>Combo Window</span>
            <span>{{ formatNumber(physics.combo_window, 1) }}s</span>
          </div>
          <input type="range" min="0.5" max="10.0" step="0.1" v-model.number="physics.combo_window"
            :disabled="stats.is_training">
        </div>
        <div class="slider-container">
          <div class="slider-label">
            <span>Max Multiplier</span>
            <span>{{ formatNumber(physics.multiplier_max, 1) }}x</span>
          </div>
          <input type="range" min="1.0" max="20.0" step="0.5" v-model.number="physics.multiplier_max"
            :disabled="stats.is_training">
        </div>
        <div class="slider-container">
          <div class="slider-label">
            <span>Base Bonus</span>
            <span>{{ formatNumber(physics.base_combo_bonus, 0) }}</span>
          </div>
          <input type="range" min="0" max="1000" step="10" v-model.number="physics.base_combo_bonus"
            :disabled="stats.is_training">
        </div>
      </div>

      <!-- Camera Group -->
      <div class="group-header" @click="toggleGroup('camera')">
        <span>Camera Settings</span>
        <span class="arrow" :class="{ rotated: groupsExpanded.camera }">▼</span>
      </div>
      <div v-if="groupsExpanded.camera" class="group-content">
        <div style="margin-bottom: 10px; color: #4caf50; font-size: 0.9em; font-weight: bold;">2D View Camera</div>
        <div class="slider-container">
          <div class="slider-label">
            <span>Camera Pitch</span>
            <span>{{ formatNumber(physics.camera_pitch, 1) }}°</span>
          </div>
          <input type="range" min="0" max="90" step="1" v-model.number="physics.camera_pitch"
            :disabled="stats.is_training">
        </div>
        <div class="slider-container">
          <div class="slider-label">
            <span>Camera X</span>
            <span>{{ formatNumber(physics.camera_x, 2) }}x</span>
          </div>
          <input type="range" min="0.0" max="1.0" step="0.05" v-model.number="physics.camera_x"
            :disabled="stats.is_training">
        </div>
        <div class="slider-container">
          <div class="slider-label">
            <span>Camera Y</span>
            <span>{{ formatNumber(physics.camera_y, 2) }}x</span>
          </div>
          <input type="range" min="0.5" max="3.0" step="0.1" v-model.number="physics.camera_y"
            :disabled="stats.is_training">
        </div>
        <div class="slider-container">
          <div class="slider-label">
            <span>Camera Z</span>
            <span>{{ formatNumber(physics.camera_z, 2) }}x</span>
          </div>
          <input type="range" min="0.5" max="3.0" step="0.1" v-model.number="physics.camera_z"
            :disabled="stats.is_training">
        </div>
        <div class="slider-container">
          <div class="slider-label">
            <span>Camera Zoom</span>
            <span>{{ formatNumber(physics.camera_zoom, 2) }}x</span>
          </div>
          <input type="range" min="0.5" max="4.0" step="0.1" v-model.number="physics.camera_zoom"
            :disabled="stats.is_training">
        </div>

        <div class="setting-group" style="margin-top: 10px; border-top: 1px solid #333; padding-top: 10px;">
          <label>Presets</label>
          <div style="display: flex; gap: 5px;">
            <select :value="selectedPreset" @change="$emit('update:selectedPreset', $event.target.value); $emit('apply-preset', $event.target.value)"
              style="flex: 1; background: #222; color: #fff; border: 1px solid #444; padding: 5px;">
              <option value="" disabled>Select Preset</option>
              <option v-for="(preset, name) in cameraPresets" :key="name" :value="name">{{ name }}
              </option>
            </select>
            <button @click="savePreset" :disabled="stats.is_training"
              style="background: #27ae60; border: none; color: white; padding: 5px 10px; cursor: pointer;">Save</button>
            <button @click="deletePreset" :disabled="stats.is_training"
              style="background: #c0392b; border: none; color: white; padding: 5px 10px; cursor: pointer;">Del</button>
          </div>
        </div>
      </div>

      <!-- Tilt Group -->
      <div class="group-header" @click="toggleGroup('tilt')">
        <span>Tilt Mechanics</span>
        <span class="arrow" :class="{ rotated: groupsExpanded.tilt }">▼</span>
      </div>
      <div v-if="groupsExpanded.tilt" class="group-content">
        <div class="slider-container">
          <div class="slider-label">
            <span>Threshold (Lower=Easier)</span>
            <span>{{ formatNumber(physics.tilt_threshold, 1) }}</span>
          </div>
          <input type="range" min="1" max="20" step="0.5" v-model.number="physics.tilt_threshold"
            :disabled="stats.is_training">
        </div>

        <div class="slider-container">
          <div class="slider-label">
            <span>Nudge Cost</span>
            <span>{{ formatNumber(physics.nudge_cost, 1) }}</span>
          </div>
          <input type="range" min="0.1" max="10" step="0.1" v-model.number="physics.nudge_cost"
            :disabled="stats.is_training">
        </div>

        <div class="slider-container">
          <div class="slider-label">
            <span>Recovery (Decay)</span>
            <span>{{ formatNumber(physics.tilt_decay, 3) }}</span>
          </div>
          <input type="range" min="0.001" max="0.2" step="0.001" v-model.number="physics.tilt_decay"
            :disabled="stats.is_training">
        </div>
      </div>

      <div style="margin-top: auto; padding-top: 20px;">
        <button class="control-btn" @click="$emit('reset-config')" :disabled="stats.is_training"
          style="width: 100%; background-color: #d32f2f;">Reset Physics</button>
      </div>
    </div>

    <!-- Training Tab -->
    <div v-show="activeTab === 'training'" class="tab-content">
      <div class="setting-group">
        <label>Model Name</label>
        <input type="text" v-model="trainingConfig.modelName" :disabled="stats.is_training"
          style="width: 80%; padding: 8px; background: #333; color: #fff; border: 1px solid #444; border-radius: 4px; margin-top: 5px;">
      </div>
      <div class="setting-group">
        <label>Timesteps</label>
        <input type="number" v-model="trainingConfig.timesteps" :disabled="stats.is_training"
          style="width: 80%; padding: 8px; background: #333; color: #fff; border: 1px solid #444; border-radius: 4px; margin-top: 5px;">
      </div>
      <div class="setting-group">
        <label>Learning Rate</label>
        <input type="number" v-model="trainingConfig.learningRate" step="0.0001" :disabled="stats.is_training"
          style="width: 80%; padding: 8px; background: #333; color: #fff; border: 1px solid #444; border-radius: 4px; margin-top: 5px;">
      </div>

      <div v-if="stats.is_training" style="margin-top: 15px;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 5px; font-size: 0.9em; color: #ccc;">
          <span>Progress <span v-if="stats.model_name" style="color: #4caf50;">({{ stats.model_name }})</span></span>
          <span>{{ Math.round(stats.training_progress * 100) }}%</span>
        </div>
        <div style="width: 100%; height: 10px; background: #333; border-radius: 5px; overflow: hidden;">
          <div
            :style="{ width: (stats.training_progress * 100) + '%', height: '100%', background: '#4caf50', transition: 'width 0.3s' }">
          </div>
        </div>
        <div style="margin-top: 5px; font-size: 0.8em; color: #aaa; display: flex; justify-content: space-between;">
          <span>Steps: {{ formatNumber(stats.current_step) }} / {{ formatNumber(stats.total_steps) }}</span>
          <span v-if="stats.eta_seconds">ETA: {{ formatTime(stats.eta_seconds) }}</span>
        </div>

        <!-- PPO Metrics Grid -->
        <div style="margin-top: 15px; display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 0.8em;">
          <div class="metric-box">
              <span class="metric-label">Mean Length</span>
              <span class="metric-value">{{ formatNumber(stats.ep_len_mean || 0, 1) }}</span>
          </div>
          <div class="metric-box">
              <span class="metric-label">Mean Reward</span>
              <span class="metric-value">{{ formatNumber(stats.ep_rew_mean || 0, 2) }}</span>
          </div>
          <div class="metric-box">
              <span class="metric-label">FPS</span>
              <span class="metric-value">{{ stats.fps || 0 }}</span>
          </div>
          <div class="metric-box">
              <span class="metric-label">Expl. Var</span>
              <span class="metric-value">{{ formatNumber(stats.explained_variance || 0, 3) }}</span>
          </div>
          <div class="metric-box">
            <span class="metric-label">Loss</span>
            <span class="metric-value">{{ formatNumber(stats.loss || 0, 3) }}</span>
          </div>
          <div class="metric-box">
            <span class="metric-label">Entropy</span>
            <span class="metric-value">{{ formatNumber(stats.entropy_loss || 0, 3) }}</span>
          </div>
          <div class="metric-box">
            <span class="metric-label">Value Loss</span>
            <span class="metric-value">{{ formatNumber(stats.value_loss || 0, 3) }}</span>
          </div>
          <div class="metric-box">
            <span class="metric-label">Policy Loss</span>
            <span class="metric-value">{{ formatNumber(stats.policy_gradient_loss || 0, 4) }}</span>
          </div>
        </div>
      </div>

      <div v-if="stats.is_training" style="margin-top: 20px; background: #1a1a1a; padding: 15px; border-radius: 8px; border: 1px solid #333;">
        <h4 style="margin: 0 0 10px 0; color: #ccc; font-size: 0.9em;">Training Metrics</h4>
        <highcharts :options="trainingChartOptions" ref="trainingChart" style="width:100%; height:250px;"></highcharts>
      </div>

      <div style="margin-top: auto; padding-top: 20px; display: flex; gap: 10px;">
        <button class="control-btn" style="flex: 1; background-color: #4caf50;" @click="startTraining"
          :disabled="stats.is_training">Start Training</button>
        <button class="control-btn" style="flex: 1; background-color: #e74c3c;" @click="stopTraining"
          :disabled="!stats.is_training">Stop</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, watch, computed } from 'vue'

const props = defineProps({
  physics: Object,
  stats: Object,
  cameraPresets: Object,
  models: Array,
  layouts: Array,
  selectedModel: String,
  selectedLayout: String,
  selectedPreset: String,
  selectedDifficulty: String,
  showFlipperZones: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['update-physics', 'reset-config', 'start-training', 'stop-training', 'apply-preset', 'save-preset', 'delete-preset', 'update:selectedModel', 'update:selectedLayout', 'update:selectedPreset', 'load-model', 'change-layout', 'update-difficulty', 'save-new-layout', 'save-layout', 'update:showFlipperZones'])

const activeTab = ref('settings')
const showZones = ref(props.showFlipperZones)

// Watch for prop changes and sync local state
watch(() => props.showFlipperZones, (newValue) => {
  showZones.value = newValue
})

// selectedPreset is now a prop
const trainingConfig = reactive({
  modelName: 'ppo_pinball',
  timesteps: 100000,
  learningRate: 0.0003
})

const saveLayout = () => {
  if (confirm("Overwrite current layout?")) {
    emit('save-layout')
  }
}

const saveLayoutAs = () => {
  const name = prompt("Enter name for new layout:")
  if (name) {
    emit('save-layout-as', name)
  }
}

const saveLayoutSettings = () => {
  if (confirm("Save current physics settings to the active layout file?")) {
    emit('save-layout-settings')
  }
}

const savePreset = () => {
  if (props.selectedPreset) {
    if (confirm(`Overwrite camera view '${props.selectedPreset}'?`)) {
      emit('save-preset', props.selectedPreset)
    }
  }
}

const savePresetAs = () => {
  const name = prompt("Enter name for new camera view:")
  if (name) {
    emit('save-preset', name)
  }
}

const updateShowZones = () => {
    emit('update:showFlipperZones', showZones.value)
}

const groupsExpanded = reactive({
  ball: false,
  flipper: false,
  rails: false,
  zones: false,
  combo: false,
  tilt: false,
  camera: false
})

const toggleGroup = (group) => {
  groupsExpanded[group] = !groupsExpanded[group]
}

const formatNumber = (num, decimals = 0) => {
  if (num === undefined || num === null) return '0'
  return num.toLocaleString(undefined, {
    minimumFractionDigits: decimals, maximumFractionDigits: decimals
  })
}

const formatTime = (seconds) => {
  if (!seconds) return '--'
  if (seconds < 60) return `${Math.round(seconds)}s`
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = Math.round(seconds % 60)
  return `${minutes}m ${remainingSeconds}s`
}

const updatePhysics = (param, value) => {
  const val = value !== undefined ? value : props.physics[param]
  emit('update-physics', param, val)
}

const applyPreset = () => {
  emit('apply-preset', props.selectedPreset)
}



const deletePreset = () => {
  if (props.selectedPreset && confirm(`Delete preset "${props.selectedPreset}"?`)) {
    emit('delete-preset', props.selectedPreset)
    emit('update:selectedPreset', '')
  }
}

const startTraining = () => {
  emit('start-training', {
    ...trainingConfig,
    layout: props.selectedLayout,
    physics: props.physics
  })
}

// Training chart data
const trainingChartData = reactive({
  timestamps: [],
  mean_reward: [],
  loss: [],
  entropy_loss: [],
  value_loss: [],
  explained_variance: [],
  updateCount: 0 // Track updates for sampling
})

const trainingChartOptions = computed(() => ({
  chart: {
    type: 'line',
    backgroundColor: 'transparent',
    animation: false
  },
  title: { text: null },
  credits: { enabled: false },
  time: { useUTC: false },
  xAxis: {
    type: 'datetime',
    gridLineColor: '#333',
    labels: { style: { color: '#999' } }
  },
  yAxis: [
    { // Primary Y-axis (Reward)
      title: { text: 'Reward', style: { color: '#4caf50' } },
      labels: { style: { color: '#4caf50' } },
      gridLineColor: '#333'
    },
    { // Secondary Y-axis (Loss)
      title: { text: 'Loss', style: { color: '#f44336' } },
      labels: { style: { color: '#f44336' } },
      opposite: true,
      gridLineColor: '#333'
    }
  ],
  legend: {
    itemStyle: { color: '#ccc' },
    itemHoverStyle: { color: '#fff' }
  },
  tooltip: {
    shared: true,
    backgroundColor: '#1a1a1a',
    borderColor: '#444',
    style: { color: '#ccc' }
  },
  plotOptions: {
    line: {
      marker: { 
        enabled: false,
        states: {
          hover: {
            enabled: true,
            radius: 4
          }
        }
      },
      lineWidth: 2,
      states: {
        hover: {
          lineWidthPlus: 1
        }
      }
    }
  },
  series: [
    {
      name: 'Mean Reward',
      data: trainingChartData.mean_reward,
      color: '#4caf50',
      yAxis: 0
    },
    {
      name: 'Loss',
      data: trainingChartData.loss,
      color: '#f44336',
      yAxis: 1
    },
    {
      name: 'Entropy Loss',
      data: trainingChartData.entropy_loss,
      color: '#ff9800',
      yAxis: 1
    },
    {
      name: 'Value Loss',
      data: trainingChartData.value_loss,
      color: '#2196f3',
      yAxis: 1
    },
    {
      name: 'Explained Variance',
      data: trainingChartData.explained_variance,
      color: '#9c27b0',
      yAxis: 0
    }
  ]
}))

// Watch for stats updates and add to chart
watch(() => props.stats, (newStats) => {
  if (newStats.is_training && newStats.current_step) {
    trainingChartData.updateCount++
    
    // Sample every 5th update to keep chart lightweight
    if (trainingChartData.updateCount % 5 !== 0) {
      return
    }
    
    const timestamp = Date.now()
    
    // Add sampled data points
    if (newStats.ep_rew_mean !== undefined) {
      trainingChartData.mean_reward.push([timestamp, newStats.ep_rew_mean || 0])
    }
    if (newStats.loss !== undefined) {
      trainingChartData.loss.push([timestamp, newStats.loss || 0])
    }
    if (newStats.entropy_loss !== undefined) {
      trainingChartData.entropy_loss.push([timestamp, newStats.entropy_loss || 0])
    }
    if (newStats.value_loss !== undefined) {
      trainingChartData.value_loss.push([timestamp, newStats.value_loss || 0])
    }
    if (newStats.explained_variance !== undefined) {
      trainingChartData.explained_variance.push([timestamp, newStats.explained_variance || 0])
    }
  }
  
  // Clear chart data when training stops
  if (!newStats.is_training && trainingChartData.mean_reward.length > 0) {
    trainingChartData.timestamps = []
    trainingChartData.mean_reward = []
    trainingChartData.loss = []
    trainingChartData.entropy_loss = []
    trainingChartData.value_loss = []
    trainingChartData.explained_variance = []
    trainingChartData.updateCount = 0
  }
}, { deep: true })

const stopTraining = () => {
  emit('stop-training')
}
</script>

<style scoped>
#physics-controls {
  grid-area: settings;
  background: #1e1e1e;
  border-radius: 8px;
  border: 1px solid #3d3d3d;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.tabs {
  display: flex;
  gap: 5px;
  border-bottom: 2px solid #333;
  padding: 10px 10px 0 10px;
  background: #1e1e1e;
  flex-shrink: 0;
}

.tab-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
}

.tab {
  flex: 1;
  padding: 10px;
  background: #2a2a2a;
  border: none;
  border-radius: 5px 5px 0 0;
  color: #aaa;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
  user-select: none;
  -webkit-user-select: none;
}

.tab.active {
  background: #333;
  color: #4caf50;
  border-bottom: 2px solid #4caf50;
}

.tab:hover {
  background: #333;
}

.group-header {
  font-size: 0.9em;
  color: #4caf50;
  margin: 15px 0 10px 0;
  padding-bottom: 5px;
  border-bottom: 1px solid #333;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  cursor: pointer;
  user-select: none;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.group-header:hover {
  color: #66bb6a;
}

.arrow {
  transition: transform 0.3s ease;
  font-size: 0.8em;
}

.arrow.rotated {
  transform: rotate(180deg);
}

.group-content {
  padding-left: 5px;
}

label {
  font-size: 0.9em;
  color: #4caf50;
  margin: 15px 0 10px 0;
  padding-bottom: 5px;
  border-bottom: 1px solid #333;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: block;
}

.slider-container {
  margin-bottom: 15px;
}

.slider-label, .checkbox-label {
  display: flex;
  justify-content: space-between;
  margin-bottom: 5px;
  font-size: 0.9em;
  color: #ccc;
}

input[type="range"] {
  width: 100%;
  height: 6px;
  border-radius: 3px;
  background: #333;
  outline: none;
  -webkit-appearance: none;
  appearance: none;
}

input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #4caf50;
  cursor: pointer;
  box-shadow: 0 0 4px rgba(76, 175, 80, 0.5);
}

input[type="range"]::-moz-range-thumb {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #4caf50;
  cursor: pointer;
  border: none;
  box-shadow: 0 0 4px rgba(76, 175, 80, 0.5);
}

.setting-group {
  margin-bottom: 15px;
}

.setting-group label {
  border-bottom: none;
  margin: 0 0 5px 0;
  padding-bottom: 0;
  color: #ccc;
  text-transform: none;
}

.control-btn {
  padding: 10px 15px;
  background-color: #333;
  color: #fff;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  font-size: 14px;
  transition: background-color 0.2s;
  user-select: none;
  -webkit-user-select: none;
}

.control-btn:disabled {
  background-color: #222 !important;
  color: #666;
  cursor: not-allowed;
}

@media (max-width: 900px) {
  #physics-controls {
    position: static;
  }
}

@media (max-width: 690px) {
  #physics-controls {
    margin: 20px 0;
  }
}

.top-controls {
  padding: 15px;
  background: #252525;
  border-bottom: 1px solid #333;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.control-group {
  display: flex;
  gap: 10px;
}

.label {
  font-size: 0.7em;
  color: #aaa;
  margin-bottom: 2px;
  text-transform: uppercase;
}

.select-input {
  width: 100%;
  padding: 8px;
  background: #333;
  color: #fff;
  border: 1px solid #444;
  border-radius: 4px;
  font-size: 14px;
}

.select-input:focus {
  border-color: #4caf50;
  outline: none;
}
.metric-box {
  background: #222;
  padding: 5px;
  border-radius: 4px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.metric-label {
  color: #888;
  font-size: 0.85em;
  margin-bottom: 2px;
}

.metric-value {
  color: #eee;
  font-weight: bold;
}
</style>
