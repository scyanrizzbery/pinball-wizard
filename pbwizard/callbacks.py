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
        
        if hasattr(self.logger, 'name_to_value'):
            # Extract training metrics from SB3 logger
            stats['explained_variance'] = self.logger.name_to_value.get('train/explained_variance', 0.0)
            stats['loss'] = self.logger.name_to_value.get('train/loss', 0.0)
            stats['value_loss'] = self.logger.name_to_value.get('train/value_loss', 0.0)
            stats['policy_gradient_loss'] = self.logger.name_to_value.get('train/policy_gradient_loss', 0.0)
            stats['entropy_loss'] = self.logger.name_to_value.get('train/entropy_loss', 0.0)
            
            # Prefer smoothed mean reward if available
            if 'rollout/ep_rew_mean' in self.logger.name_to_value:
                stats['ep_rew_mean'] = self.logger.name_to_value['rollout/ep_rew_mean']

        # Check for episode completion to update game count
        for info in self.locals.get('infos', []):
            if 'episode' in info:
                self.games_played += 1
                # We can still send the raw last episode reward if needed, but the logger mean is better for charts
                # stats['last_reward'] = info['episode']['r'] 
                stats['length'] = info['episode']['l']
                stats['games_played'] = self.games_played
                
                # Update wrapper (intermediate update for responsiveness)
                self.vision_wrapper.update_training_stats(stats)
                
        # Also update timesteps every step
        self.vision_wrapper.update_training_stats(stats)
        
        return True
