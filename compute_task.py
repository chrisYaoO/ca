__all__ = ['MonteCarloPi']

import random
import multiprocessing
from tqdm import tqdm


class MonteCarloPi:
    def __init__(self):
        self.num_samples = int(5e7)
        self.num_process = 5

    def monte_carlo_pi(self, num_samples):
        inside_circle = 0
        for i in tqdm(range(num_samples)):
            x = random.uniform(-1, 1)
            y = random.uniform(-1, 1)
            if x ** 2 + y ** 2 <= 1:
                inside_circle += 1
        return inside_circle

    def run(self):
        pool = multiprocessing.Pool(processes=self.num_process)
        results = pool.map(self.monte_carlo_pi, [self.num_samples // self.num_process] * self.num_process)
        pool.close()
        pool.join()
        return 4 * sum(results) / self.num_samples
