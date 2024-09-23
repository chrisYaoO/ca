import json
import os
import re
# import psutil
import datetime
import socket
import uuid
import subprocess
# import yaml
import docker
import logging

GL_DEVICE_NO = str(uuid.uuid4())


def get_gl_device_no():
    return GL_DEVICE_NO


class DeviceMonitor:
    LOG_FORMAT = "%(asctime)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s"
    logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)

    # 获取Mac地址
    @classmethod
    def get_mac_address(cls):
        mac = uuid.UUID(int=uuid.getnode()).hex[-12:]
        return ":".join([mac[e:e + 2] for e in range(0, 11, 2)])

    # 磁盘 磁盘的使用量等等
    @classmethod
    def get_physical_device(cls):
        if not os.path.exists('../network/constant/local_client.yml'):
            device_no = get_gl_device_no()
            config = {'device_no': device_no}
            file = open('../network/constant/local_client.yml', 'a', encoding='utf-8')
            yaml.dump(config, file)
            file.close()
        file = open('../network/constant/local_client.yml', 'r', encoding='utf-8')
        config = yaml.load(file.read(), Loader=yaml.FullLoader)
        file.close()
        device_no = config['device_no']
        # 获取主机名
        hostname = socket.gethostname()
        # 获取IP
        ip = socket.gethostbyname(hostname)
        # 系统用户
        users_list = ",".join([u.name for u in psutil.users()])
        # print(u"当前有%s个用户，分别是%s" % (users_count, users_list))
        # 系统启动时间
        start_time = datetime.datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
        sys_info = {"device_name": hostname, "ip_address": ip, "mac": DeviceMonitor.get_mac_address(),
                    "user": users_list,
                    "start_time": start_time}

        # 01.cpu信息
        cpu1 = psutil.cpu_count()
        cpu2 = str(psutil.cpu_percent(interval=1)) + '%'
        # print(u"物理CPU个数 %s" % psutil.cpu_count(logical=False))
        cpu = {"amount": cpu1, "rate": cpu2}

        # 02.内存信息
        mem = psutil.virtual_memory()
        mem_total = round(mem.total / 1024 / 1024 / 1024, 2)
        mem_free = round(mem.free / 1024 / 1024 / 1024, 2)
        mem_percent = str(mem.percent) + '%'
        mem_used = round(mem.used / 1024 / 1024 / 1024, 2)
        memory = {"total": mem_total, "free": mem_free, "rate": mem_percent, "used": mem_used}

        # 03.磁盘信息(磁盘空间使用占比)
        # io = psutil.disk_partitions()
        # disk = []
        # for i in io:
        #     # print(i.device)
        #     o = psutil.disk_usage(i.device)
        #     disk_data = {"disk_name": i.device,
        #                  "total": round(o.total / (1024.0 * 1024.0 * 1024.0), 1),
        #                  "used": round(o.used / (1024.0 * 1024.0 * 1024.0), 1),
        #                  "surplus": round(o.free / (1024.0 * 1024.0 * 1024.0), 1),
        #                  "rate": psutil.disk_usage(i.device).percent}
        #     disk.append(disk_data)

        # 04.网卡，可以得到网卡属性，连接数，当前流量等信息
        net_info = psutil.net_io_counters()
        bytes_sent = '{0:.2f}'.format(net_info.bytes_recv / 1024 / 1024)  # mb
        bytes_rcvd = '{0:.2f}'.format(net_info.bytes_sent / 1024 / 1024)
        net = {"bytes_sent": bytes_sent, "bytes_rcvd": bytes_rcvd}

        # 数据字典
        # data = {"sys": sys_info, "cpu": cpu, "ddr": ddr, "disk": disk, "net": net}
        # data = {"DeviceInfo": sys_info, "cpu": cpu, "memory": memory, "net": net}
        # device_info = {"DeviceInfo": sys_info, "cpu": cpu, "memory": memory, "net": net}
        device_info = {"heart_beat": "heart_beat", "device_no": device_no, "server_no": "#", "used_cpu": cpu["rate"],
                       "core_num": cpu["amount"], "idle_memory": mem_free, "used_memory": mem_used,
                       "total_memory": mem_total, "work_status": 0, "lng": 0.000000, "lat": 0.000000, "order_value": -1,
                       "ip_address": ip}
        return device_info

    @classmethod
    def parse_container_info(cls, command):
        # print('parsing...')
        container_info = {}
        output = subprocess.check_output(command).decode()
        lines = output.strip().split('\n')
        for line in lines:
            # print(line)
            container_name, container_id, cpu_usage, mem_info = line.strip().split(':')
            command_1 = ["docker", "inspect", "--format", "{{.HostConfig.NanoCpus}}", container_id]
            cpu_limit = subprocess.check_output(command_1).decode()
            # print(cpu_limit)
            cpu_limit = float(cpu_limit) / 1e9
            cpu_perc = float(cpu_usage.strip('%')) / cpu_limit
            pattern = r"(\d+\.\d+)(MiB|GiB)\s/\s(\d+)(MiB|GiB)"
            match = re.match(pattern, mem_info)

            used_memory = float(match.group(1))  # 已使用内存量
            used_unit = match.group(2)  # 单位
            total_memory = float(match.group(3))  # 总内存量
            total_unit = match.group(4)  # 单位

            unit_conversion = {"MiB": 1, "GiB": 1024}
            used_memory *= unit_conversion.get(used_unit, 1)
            total_memory *= unit_conversion.get(total_unit, 1)

            mem_perc = round((used_memory / total_memory) * 100, 2)

            device_info = {
                "Container": container_name,
                "device_no": container_id,
                "Cpu_perc": cpu_perc,
                "Cpu_limit": cpu_limit,
                "Mem_perc": mem_perc,
                "Mem_limit": total_memory
            }
            tag = container_name[-3]
            container_info[tag] = device_info


        return container_info

    @classmethod
    def get_container_id(cls):
        try:
            with open('/proc/self/cgroup', 'r') as f:
                for line in f:
                    if '/docker/' in line:
                        # 获取容器ID部分
                        return line.split('/')[-1].strip()
        except FileNotFoundError:
            pass  # 如果文件不存在，返回None
        except Exception as e:
            print("An error occurred:", e)
        return None

    @classmethod
    def get_container_name_by_id(cls, container_id):
        try:
            client = docker.from_env()
            container_info = client.api.inspect_container(container_id)
            container_name = container_info['Name'].lstrip('/')
            return container_name
        except Exception as e:
            print("Error occurred while getting container name:", e)
        return None

    @classmethod
    def get_container_info_all(cls):
        command = ["docker", "stats", "--no-stream", "--format", "{{.Name}}:{{.ID}}:{{.CPUPerc}}:{{.MemUsage}}"]
        return cls.parse_container_info(command)

    @classmethod
    def get_container_info_id(cls, container_id):
        command = ["docker", "stats", container_id, "--no-stream", "--format",
                   "\"{{.Name}}:{{.ID}}:{{.CPUPerc}}:{{.MemUsage}}\""]
        return cls.parse_container_info(command)

    # 调用函数并传入容器 ID


if __name__ == '__main__':
    container_id='f0d6b3afa22d'
    command = ["docker", "stats", container_id, "--no-stream", "--format",
                   "{{.Name}}:{{.ID}}:{{.CPUPerc}}:{{.MemUsage}}"]
    output = subprocess.check_output(command).decode()
    print(output)
    info=DeviceMonitor.parse_container_info(command)

    print(info)
