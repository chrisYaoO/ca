from __future__ import annotations

import json
import logging
import random
from typing import Dict, Set, TypeVar

from config.common_redis_key_constant import ComRedisKeyConstant
from config.redis_boot import REDIS_TOOLS

from predis.interfaces.device_service import DeviceService


class DeviceServiceImpl(DeviceService):
    T = TypeVar('T')

    @classmethod
    def write_device_to_cache(cls, device_info: dict):
        # device set
        device_set_key = ComRedisKeyConstant.DEVICE_ONLINE_SET
        REDIS_TOOLS.sset_and_time(device_set_key, 86400, device_info['device_no'])
        # device info
        device_key = ComRedisKeyConstant.DEVICE_ONLINE_PREFIX + device_info['device_no']
        REDIS_TOOLS.set_key_value_with_ttl(device_key, json.dumps(device_info), 86400)
        # device history
        device_history = "Device_history" + device_info['device_no']
        REDIS_TOOLS.lset_time(device_history, json.dumps(device_info), 86400)

    @classmethod
    # result_msg = 'result:' + str(result) + ':' + id + ':' + str(cls.assigned_task[tag][0]) + ':' + str(time_taken)
    def write_result_to_cache(cls, client_id, result_info):
        result_key = 'RESULT_' + client_id
        REDIS_TOOLS.lset_time(result_key, 86400, json.dumps(result_info))

    @classmethod
    #
    def query_device_info_by_id(cls, device_id: str) -> dict:
        key = ComRedisKeyConstant.DEVICE_ONLINE_PREFIX + device_id
        device_info_json = REDIS_TOOLS.get(key)
        # logging.debug(f"找到设备：{device_info_json}")
        device_info = json.loads(device_info_json)
        return device_info

    @classmethod
    def write_device_to_cache_performance(cls, device_info: dict):
        logging.info(f"请求性能信息参数信息为：{device_info}")
        device_info_1 = DeviceInfo()
        device_info_1.set_device_from_dict(device_info)
        if IdleDeviceImpl.idle_devices(device_info):
            # 计算设备性能
            core_num = device_info_1.get_core_num()
            work_status = device_info_1.get_work_status()
            used_cpu = device_info_1.get_used_cpu()
            idle_memory = device_info_1.get_idle_memory()
            total_memory = device_info_1.get_total_memory()
            idle_core_num = core_num - work_status
            idle_cpu = 1.0 - float(used_cpu.strip("%"))
            high_index = -(idle_core_num * idle_cpu * idle_memory / total_memory)
            # 设备性能编号集合10秒自动销毁
            device_set_key = ComRedisKeyConstant.DEVICE_ONLINE_PERFORMANCE_SET
            REDIS_TOOLS.zset_with_ttl(device_set_key, device_info_1.get_device_no(), high_index, 10)
        else:
            logging.info(f"设备{device_info_1.get_device_no()}不满足空闲设备条件...")

    def write_device_to_cache_memory(self, device_info: dict):
        logging.info(f"请求空闲内存信息参数信息为：{device_info}")
        device_info_1 = DeviceInfo()
        device_info_1.set_device_from_dict(device_info)
        if IdleDeviceImpl.idle_devices(device_info):
            delay = device_info_1.get_idle_memory()
            # 设备空闲内存编号集合10秒自动销毁
            device_set_key = ComRedisKeyConstant.DEVICE_ONLINE_MEMORY_SET
            REDIS_TOOLS.zset_with_ttl(device_set_key, device_info_1.get_device_no(), delay, 10)
        else:
            logging.info(f"设备{device_info_1.get_device_no()}不满足空闲设备条件...")

    def write_device_to_cache_delay(self, device_info: dict):
        logging.info(f"请求距离信息参数信息为：{device_info}")
        device_info_1 = DeviceInfo()
        device_info_1.set_device_from_dict(device_info)
        if IdleDeviceImpl.idle_devices(device_info):
            delay = device_info_1.get_delay()
            # 设备延迟编号集合10秒自动销毁
            device_set_key = ComRedisKeyConstant.DEVICE_ONLINE_DELAY_SET
            REDIS_TOOLS.zset_with_ttl(device_set_key, device_info_1.get_device_no(), delay, 10)
        else:
            logging.info(f"设备{device_info_1.get_device_no()}不满足空闲设备条件...")

    @classmethod
    # 全部
    def read_device_info(cls) -> Dict[str, dict] | None:
        device_info_list = {}
        key_set = REDIS_TOOLS.sget(ComRedisKeyConstant.DEVICE_ONLINE_SET)
        if key_set is not None:
            for s in key_set:
                device_no = s.decode()
                key = ComRedisKeyConstant.DEVICE_ONLINE_PREFIX + device_no
                device_info_json = REDIS_TOOLS.get(key)
                device_info = json.loads(device_info_json)
                if device_info is not None:
                    device_info_list[device_no] = device_info
                logging.info(f"所有设备信息: {device_info_list}")
        return device_info_list

    @classmethod
    def read_device_info_random(cls, count: int) -> Dict[str, dict] | None:
        set_size = 0
        num = 0
        device_info_list = {}
        device_id_set = REDIS_TOOLS.sget(ComRedisKeyConstant.DEVICE_ONLINE_SET)
        device_id_list = list(device_id_set)
        device_size = len(device_id_set)
        if device_size != 0:
            while set_size < count and num < device_size:
                device_id = random.choice(device_id_list).decode()
                device_id_list.remove(device_id.encode())
                key = ComRedisKeyConstant.DEVICE_ONLINE_PREFIX + device_id
                device_info_json = REDIS_TOOLS.get(key)
                device_info = json.loads(device_info_json)
                if IdleDeviceImpl.idle_devices(device_info):
                    device_info_list[device_id] = device_info
                set_size = len(device_info_list)
                num = num + 1
                if set_size < count:
                    logging.info(f"请求设备数量：{count}, 实际满足条件设备数量：{set_size}, 符合条件的设备数量不足...")
                    if set_size == 0 and count == 1:
                        logging.info("无满足空闲条件设备，随机返回一台设备...")
                        device_id_set = REDIS_TOOLS.sget_count(ComRedisKeyConstant.DEVICE_ONLINE_SET, 1)
                        device_id_1 = next(iter(device_id_set)).__str__()
                        key_1 = ComRedisKeyConstant.DEVICE_ONLINE_PREFIX + device_id_1
                        device_info_1 = REDIS_TOOLS.get(key_1)
                        device_info_list[key_1] = device_info_1
                        logging.info(f"设备信息:{device_info_list}")
                    else:
                        logging.info(f"设备编号:{set(device_info_list.keys())}")
                        logging.info(f"所有设备信息:{device_info_list}")
                logging.info(f"read_device_info_random: {device_info_list}")
                return device_info_list
        else:
            logging.info("无在线设备...")
            return None

    @classmethod
    def read_device_info_delay(cls, min: float, max: float) -> Dict[str, dict] | None:
        key_set = REDIS_TOOLS.zget(ComRedisKeyConstant.DEVICE_ONLINE_DELAY_SET, min, max)
        REDIS_TOOLS.remove_range(ComRedisKeyConstant.DEVICE_ONLINE_DELAY_SET, min, max)
        logging.info(f"取出低延迟设备编号:{key_set}")
        return cls.return_device_info_map(key_set)

    @classmethod
    def read_device_info_memory(cls, min: float, max: float) -> Dict[str, dict] | None:
        key_set = REDIS_TOOLS.zget(ComRedisKeyConstant.DEVICE_ONLINE_MEMORY_SET, min, max)
        REDIS_TOOLS.remove_range(ComRedisKeyConstant.DEVICE_ONLINE_MEMORY_SET, min, max)
        logging.info(f"取出空闲内存设备编号:{key_set}")
        return cls.return_device_info_map(key_set)

    @classmethod
    # cpu
    def read_device_info_performance(cls, start: float, end: float) -> Dict[str, dict] | None:
        key_set = REDIS_TOOLS.zget(ComRedisKeyConstant.DEVICE_ONLINE_PERFORMANCE_SET, start, end)
        REDIS_TOOLS.remove_range(ComRedisKeyConstant.DEVICE_ONLINE_PERFORMANCE_SET, start, end)
        logging.info(f"取出高性能设备编号:{key_set}")
        return cls.return_device_info_map(key_set)

    @classmethod
    def return_device_info_map(cls, key_set: Set[T]) -> Dict[str, dict] | None:
        device_info_list = {}
        if key_set is not None:
            for s in key_set:
                device_no = s.decode()
                key = ComRedisKeyConstant.DEVICE_ONLINE_PREFIX + device_no
                device_info_json = REDIS_TOOLS.get(key)
                device_info = json.loads(device_info_json)
                if device_info is not None:
                    device_info_list[device_no] = device_info
            logging.info(f"所有设备信息: {device_info_list}")
            return device_info_list
        else:
            return None

    @classmethod
    def return_device_list(cls):
        device_set_key = ComRedisKeyConstant.DEVICE_ONLINE_SET
        return REDIS_TOOLS.sget(device_set_key)

    @classmethod
    def flush_database(cls):
        REDIS_TOOLS.r.flushdb()
        print('db flushed')
        return True

    @classmethod
    def query_device_history_by_id(cls, device_id: str, count: int):
        device_history_key = "Device_history" + device_id
        # 获取列表的长度
        list_length = REDIS_TOOLS.r.llen(device_history_key)

        # 获取最新的五个值
        start_index = max(0, list_length - count)  # 起始索引
        end_index = list_length - 1  # 结束索引

        # 使用 LRANGE 命令获取列表的最新五个值
        latest_values = REDIS_TOOLS.r.lrange(device_history_key, start_index, end_index)
        return latest_values
