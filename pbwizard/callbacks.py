from stable_baselines3.common.callbacks import BaseCallback
import numpy as np
import progressbar


class ProgressBarCallback(BaseCallback):
    """
    Callback for displaying a progress bar during training.
    """
    def __init__(self, total_timesteps, verbose=0):
        super(ProgressBarCallback, self).__init__(verbose)
        self.total_timesteps = total_timesteps
        self.pbar = None

    def _on_training_start(self) -> None:
        widgets = [
            'Training: ', progressbar.Percentage(),
            ' ', progressbar.Bar(marker='=', left='[', right=']'),
            ' ', progressbar.Counter(), f'/{self.total_timesteps} Steps',
            ' ', progressbar.ETA(),
        ]
        self.pbar = progressbar.ProgressBar(max_value=self.total_timesteps, widgets=widgets)
        self.pbar.start()

    def _on_step(self) -> bool:
        if self.pbar:
            self.pbar.update(min(self.num_timesteps, self.total_timesteps))
        return True

    def _on_training_end(self) -> None:
        if self.pbar:
            self.pbar.finish()


class WebStatsCallback(BaseCallback):
    """
    Callback for updating the web interface with training statistics.
    """
    def __init__(self, vision_wrapper, verbose=0):
        super(WebStatsCallback, self).__init__(verbose)
        self.vision_wrapper = vision_wrapper
        self.games_played = 0

    def _on_step(self) -> bool:
        # Extract stats
        stats = {
            'timesteps': self.num_timesteps,
            'mean_reward': 0.0,
            'games_played': self.games_played
        }
        
        # Try to get mean reward from logger (it might not be available every step)
        # SB3 logs 'rollout/ep_rew_mean'
        # We can also look at self.locals['infos'] for immediate reward if needed, 
        # but mean reward is better for tracking progress.
        # Accessing internal logger values is a bit hacky but standard for this.
        
        # A more robust way for immediate feedback might be to track it ourselves 
        # or rely on what SB3 exposes.
        
        # Let's check if we can get the last episode reward from the monitor wrapper if present
        # Or just use the safe_mean from the logger if available
        
        # For now, let's just send the timesteps. 
        # To get ep_rew_mean, we usually need to wait for the end of an episode or log interval.
        
        # However, we can check self.locals['infos'] for 'episode' key which Monitor wrapper adds
        for info in self.locals.get('infos', []):
            if 'episode' in info:
                self.games_played += 1
                stats['mean_reward'] = info['episode']['r'] # Last episode reward
                stats['length'] = info['episode']['l']
                stats['games_played'] = self.games_played
                
                # Update wrapper
                self.vision_wrapper.update_training_stats(stats)
                
        # Also update timesteps every step
        self.vision_wrapper.update_training_stats({'timesteps': self.num_timesteps})
        
        return True
