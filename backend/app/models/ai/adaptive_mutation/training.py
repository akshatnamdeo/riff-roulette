import gym
from gym import spaces
import numpy as np
from stable_baselines3 import DQN

class MutationEnv(gym.Env):
    def __init__(self):
        super(MutationEnv, self).__init__()
        self.action_space = spaces.Discrete(3)
        self.observation_space = spaces.Box(low=0, high=100, shape=(3,), dtype=np.float32)
        self.state = np.array([50.0, 50.0, 50.0])
        self.current_step = 0

    def step(self, action):
        self.current_step += 1
        if action == 0:
            self.state = self.state - np.random.rand(3) * 5
        elif action == 2:
            self.state = self.state + np.random.rand(3) * 5
        self.state = np.clip(self.state, 0, 100)
        reward = float(np.sum(self.state)) / 300
        done = self.current_step >= 50 or np.mean(self.state) >= 95 or np.mean(self.state) <= 5
        info = {}
        return self.state, reward, done, info

    def reset(self):
        self.state = np.array([50.0, 50.0, 50.0])
        self.current_step = 0
        return self.state

env = MutationEnv()
model = DQN("MlpPolicy", env, verbose=1)
model.learn(total_timesteps=10000)
model.save("dqn_mutation_agent")
