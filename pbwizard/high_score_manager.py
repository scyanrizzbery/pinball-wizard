
import json
import os
import shutil
import logging
from datetime import datetime

logger = logging.getLogger("pbwizard.high_score_manager")

class HighScoreManager:
    def __init__(self, filepath="highscores.json"):
        self.filepath = filepath
        self.scores = {} # keyed by layout name
        self.load_scores()

    def load_scores(self):
        """Load scores from JSON file, migrating legacy format if needed."""
        if not os.path.exists(self.filepath):
            self.scores = {}
            return

        try:
            with open(self.filepath, 'r') as f:
                data = json.load(f)

            if isinstance(data, list):
                logger.info("Detected legacy high score format (list). Migrating to dict...")
                self._migrate_legacy_scores(data)
                self.save_scores()
            elif isinstance(data, dict):
                self.scores = data
            else:
                logger.error(f"Unknown high score format: {type(data)}")
                self.scores = {}

        except Exception as e:
            logger.error(f"Failed to load high scores: {e}")
            self.scores = {}

    def _migrate_legacy_scores(self, data_list):
        """Convert list of scores to dict keyed by layout."""
        self.scores = {}
        for entry in data_list:
            layout = entry.get('layout', 'default')
            if layout not in self.scores:
                self.scores[layout] = []
            self.scores[layout].append(entry)
        
        # Sort all lists
        for layout in self.scores:
            self.scores[layout].sort(key=lambda x: x['score'], reverse=True)
            
        logger.info(f"Migration complete. Found {len(data_list)} scores across {len(self.scores)} layouts.")

    def save_scores(self):
        """Save scores to JSON file."""
        try:
            # Create backup before saving if migrating? 
            # Nah, standard save is fine.
            with open(self.filepath, 'w') as f:
                json.dump(self.scores, f, indent=2)
            logger.info("High scores saved.")
        except Exception as e:
            logger.error(f"Failed to save high scores: {e}")

    def add_score(self, layout, score_data):
        """Add a new score for a specific layout."""
        if layout not in self.scores:
            self.scores[layout] = []
        
        # Add timestamp if missing
        if 'timestamp' not in score_data:
            import time
            score_data['timestamp'] = time.time()
        if 'date' not in score_data:
            score_data['date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
        self.scores[layout].append(score_data)
        
        # Sort and keep top 50?
        self.scores[layout].sort(key=lambda x: x['score'], reverse=True)
        self.scores[layout] = self.scores[layout][:50]
        
        self.save_scores()

    def get_scores(self, layout):
        """Get scores for a specific layout."""
        return self.scores.get(layout, [])

    def get_high_score(self, layout):
        """Get the highest score for a layout."""
        scores = self.get_scores(layout)
        if scores:
            return scores[0]['score']
        return 0
