from stable_baselines3 import DQN
from typing import Any
import numpy as np

class AdaptiveMutationService:
    """
    This service loads a pre-trained RL agent that adjusts mutation parameters.
    The agent expects a state vector (e.g., performance metrics) and returns an action:
        0: Decrease mutation strength
        1: Maintain mutation strength
        2: Increase mutation strength
    """
    def __init__(self, model_path: str = "trained/adaptive_mutation/dqn_mutation_agent"):
        # Load the trained RL agent from the specified zip file.
        self.model = DQN.load(model_path)

    def get_action(self, state: np.ndarray) -> int:
        """
        Given a state vector, return the action chosen by the RL agent.
        :param state: A numpy array representing the performance metrics.
        :return: An integer action (0, 1, or 2).
        """
        action, _ = self.model.predict(state)
        return int(action)

    def adjust_mutation_strength(self, current_strength: float, state: np.ndarray) -> float:
        """
        Adjusts the current mutation strength based on the RL agent's action.
        :param current_strength: Current mutation strength (e.g., 0.1 to 1.0)
        :param state: A numpy array representing performance metrics.
        :return: New mutation strength after adjustment.
        """
        action = self.get_action(state)
        if action == 0:
            # Decrease mutation strength by a fixed step.
            new_strength = max(0.1, current_strength - 0.1)
        elif action == 2:
            # Increase mutation strength by a fixed step.
            new_strength = min(1.0, current_strength + 0.1)
        else:
            # Maintain current strength.
            new_strength = current_strength
        return new_strength
