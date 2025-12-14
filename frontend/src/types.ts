export interface Point {
    x: number;
    y: number;
}

export interface Zone {
    id: string;
    type: string;
    points: Point[];
}

export interface Rail {
    id?: string;
    p1: Point;
    p2: Point;
    [key: string]: any;
}

export interface Bumper {
    x: number;
    y: number;
    radius_ratio: number;
    value: number;
    [key: string]: any;
}

export interface DropTarget {
    x: number;
    y: number;
    width: number;
    height: number;
    [key: string]: any;
}

export interface RewardsConfig {
    score_log_scale: number;
    combo_increase_factor: number;
    multiplier_increase_factor: number;
    flipper_penalty: number;
    bumper_hit: number;
    drop_target_hit: number;
    rail_hit: number;
    [key: string]: number;
}

export interface PhysicsConfig {
    gravity: number;
    friction: number;
    restitution: number;
    flipper_speed: number;
    flipper_resting_angle: number;
    flipper_stroke_angle: number;
    flipper_length: number;
    flipper_width: number;
    flipper_spacing: number;
    flipper_tip_width: number;
    flipper_tip_width: number;
    flipper_elasticity: number;
    ball_mass: number;
    tilt_threshold: number;
    nudge_cost: number;
    tilt_decay: number;
    camera_pitch: number;
    camera_x: number;
    camera_y: number;
    camera_z: number;
    camera_zoom: number;
    combo_window: number;
    multiplier_max: number;
    plunger_release_speed: number;
    launch_angle: number;
    base_combo_bonus: number;
    combo_multiplier_enabled: boolean;
    flipper_impulse_multiplier: number;
    bumper_force: number;
    bumper_respawn_time: number;
    drop_target_cooldown: number;
    zones: Zone[];
    rails: Rail[];
    bumpers: Bumper[];
    drop_targets?: DropTarget[];
    mothership?: any;
    rail_x_offset: number;
    rail_y_offset: number;
    god_mode: boolean;
    left_flipper_pos_x: number;
    left_flipper_pos_y: number;
    right_flipper_pos_x: number;
    right_flipper_pos_y: number;
    [key: string]: any; // Allow dynamic indexing
}

export interface GameStats {
    score: number;
    high_score: number;
    balls: number;
    balls_remaining: number;
    current_ball: number;
    ball_count: number;
    games_played: number;
    game_history: any[];
    timesteps: number;
    mean_reward: number;
    is_training: boolean;
    nudge: any;
    tilt_value: number;
    is_tilted: boolean;
    training_progress: number;
    current_step: number;
    total_steps: number;
    eta_seconds: number;
    is_simulation: boolean;
    combo_count: number;
    combo_timer: number;
    score_multiplier: number;
    combo_active: boolean;
    hash: string;
    seed: any;
    last_score: number;
    game_over: boolean;
    is_high_score: boolean;
    is_replay?: boolean;
    // Training stats
    ep_rew_mean?: number;
    explained_variance?: number;
    loss?: number;
    value_loss?: number;
    policy_gradient_loss?: number;
    entropy_loss?: number;
    high_scores?: HighScoreEntry[];
    [key: string]: any;
}

export interface HighScoreEntry {
    score: number;
    model: string;
    layout: string;
    date: string;
    timestamp: number;
}
