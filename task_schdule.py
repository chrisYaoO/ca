import random
import numpy as np
from config.config import *

class Static:

    @classmethod
    def random_assign(cls, num_task: int, device_config: dict):
        num_device = len(device_config)
        assigned_task = {str(device_id + 1): [] for device_id in range(num_device)}
        for i in range(num_task):
            device_no = random.randint(1, num_device)
            assigned_task[str(device_no)].append(i + 1)
        return assigned_task

    @classmethod
    def min_min(cls, num_task: int, device_config: dict):
        num_device = len(device_config)
        device_time = np.zeros(num_device)
        assigned_task = {str(device_id + 1): [] for device_id in range(num_device)}
        for i in range(num_device):
            device_time[i] = device_time[i] + 1 / device_config[str(i + 1)]['num_cpu']
        for i in range(num_task):
            # print('device time: ', device_time)
            min_index = np.argmin(device_time)
            device_time[min_index] += 1 / device_config[str(min_index + 1)]['num_cpu']
            assigned_task[str(min_index + 1)].append(i + 1)
        return assigned_task

    @classmethod
    def base_assign(cls, num_task: int, device_config: dict):
        num_device = len(device_config)
        assigned_task = {str(device_id + 1): [] for device_id in range(num_device)}
        i = 0
        for i in range(num_task):
            assigned_task[str(i % num_device + 1)].append(i+1)
        return assigned_task


if __name__ == '__main__':
    # device_config = {'1': {'num_cpu': 1 / 3}, '2': {'num_cpu': 1 / 2}, '3': {'num_cpu': 1 / 4},
    #                  '4': {'num_cpu': 1 / 5}}

    print(Static.base_assign(10, device_config))

# print(Static.random_assign(5))
