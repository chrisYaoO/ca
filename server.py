import socket
from config.config import *
import threading
from task_schdule import *
import json
import docker
import logging
import subprocess
import time
from device_service_impl import DeviceServiceImpl
from device_monitor import DeviceMonitor


# 远程容器,还有问题
def get_remote_docker_client(remote_host_ip, port=6379):
    base_url = f'tcp://{remote_host_ip}:{port}'
    client = docker.DockerClient(base_url=base_url)
    return client
    # remote_host_ip = '192.168.3.174'
    # client = get_remote_docker_client(remote_host_ip)
    #
    # # 列出远程主机上的所有容器
    # containers = client.containers.list(all=True)
    # for container in containers:
    #     print(container.id, container.name)


def generate_truncated_normal(mean, std_dev, lower, upper):
    sample = random.gauss(mean, std_dev)
    sample = round(sample, 2)
    if lower <= sample <= upper:
        return sample
    else:
        return generate_truncated_normal(mean, std_dev, lower, upper)


# 获取容器id


def get_all_container_ids():
    client = docker.from_env()  # 创建 Docker 客户端
    containers = client.containers.list(all=True)  # 列出所有容器，包括停止的容器
    container_ids = [container.id for container in containers]
    return container_ids


def get_container_tag_by_id(container_id):
    name = DeviceMonitor.get_container_name_by_id(container_id)
    return name[-3]


class Server:
    # DeviceServiceImpl.flush_database()

    host = HOST
    port = PORT
    # 设定任务数量和设备配置，根据算法分配任务给不同容器
    num_task = 10
    num_task_finished = 0
    num_device = 0
    device_config = {'1': {'num_cpu': 1 / 3}, '2': {'num_cpu': 1 / 2}, '3': {'num_cpu': 1 / 4}, '4': {'num_cpu': 1 / 5}}
    assigned_task = Static.base_assign(10, device_config)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # 创建socket对象
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 128000000)

    address = addr = (host, port)
    sock.bind(address)  # 绑定地址和端口
    LOG_FORMAT = "%(asctime)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s"
    logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)

    @classmethod
    def server(cls, ca=False):
        logging.info('server is listening on port {}'.format(cls.port))
        data_process_thread = threading.Thread(target=cls.msg_process)
        data_process_thread.start()

        if ca:
            cpu_thread = threading.Thread(target=cls.cpu_change_ca)
            cpu_thread.start()
        else:
            cpu_thread = threading.Thread(target=cls.cpu_change)
            cpu_thread.start()

    @classmethod
    def msg_process(cls):
        while True:
            data, addr = cls.sock.recvfrom(1024)
            data = data.decode('utf-8')
            print(data)

            if data.startswith('delay'):
                # logging.info(data)
                data = data.split(':')
                client_id = data[-1].rstrip()
                monitor_thread = threading.Thread(target=cls.update_container_info_to_cache, args=(client_id,))
                monitor_thread.start()

            elif data.startswith('hello'):
                logging.info(data)
                client_id = data.split(':')[-1].rstrip()
                cls.num_device += 1
                logging.info(f'sending task to {client_id}')
                cls.send_compute_task(addr)

            elif data.startswith('result'):
                logging.info(data)
                data = data.split(':')
                result = data[1]
                client_id = data[2].rstrip()
                time_taken = data[-1]
                cls.num_task_finished += 1
                print(cls.num_task_finished)
                result_info = result + ':' + time_taken
                DeviceServiceImpl.write_result_to_cache(client_id, result_info)
                logging.info(f'result saved: {result_info}', )

    @classmethod
    def container_monitor(cls):
        while True:
            if cls.num_device > 0 and cls.num_task_finished < cls.num_task:
                client_ids = get_all_container_ids()
                for client_id in client_ids:
                    cls.update_container_info_to_cache(client_id)
            time.sleep(2)

    @classmethod
    def update_container_info_to_cache(cls, client_id):
        try:
            device_infos = DeviceMonitor.get_container_info_id(client_id)
            # print(device_infos)
            device_info = next(iter(device_infos.values()))
            # print(device_info)
            DeviceServiceImpl.write_device_to_cache(device_info)
        except Exception as e:
            print("Error updating container info and cache:", e)
        time.sleep(5)

    @classmethod
    def send_compute_task(cls, addr):
        json_data = json.dumps(cls.assigned_task)
        try:
            cls.sock.sendto(json_data.encode('utf-8'), addr)
        except (OSError, cls.sock.error) as e:
            print("assignment sent error", e)
            return e.errno

        with open('cnn.py', 'rb') as file:
            file_data = file.read()
        chunks = [file_data[i:i + CHUNK_SIZE] for i in range(0, len(file_data), CHUNK_SIZE)]
        for chunk in chunks:
            try:
                cls.sock.sendto(chunk, addr)
            except (OSError, cls.sock.error) as e:
                print("chunk sent error", e)
                return e.errno
        try:
            cls.sock.sendto('EOF'.encode('utf-8'), addr)
            logging.info("file sent success")
        except (OSError, cls.sock.error) as e:
            print("EOF sent error", e)
            return e.errno

    @classmethod
    def update_container_config(cls, container_id: str, cpu_limit: float):
        command = ["docker", "update", "--cpus=" + str(cpu_limit), container_id]
        update_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        update_output, update_error = update_process.communicate()
        if update_process.returncode:
            # logging.info("update success:", update_output.decode('utf-8'))
            logging.info("update error:", update_error.decode('utf-8'))

    # 模拟cpu资源减少的情况，当没有动态调度时，只能减少cpu使用资源，无法扩张
    @classmethod
    def cpu_change(cls):
        device_infos = DeviceMonitor.get_container_info_all()
        while cls.num_task_finished < cls.num_task:
            for tag, device_info in device_infos.items():
                num_cpu = device_info['Cpu_limit']
                cpu_new = generate_truncated_normal(num_cpu, 1, num_cpu - 1, num_cpu + 1)
                if cpu_new < num_cpu:
                    logging.info(f'update device {tag}')
                    cls.update_container_config(device_info['device_no'], cpu_new)
                    device_infos[tag]['Cpu_limit'] = cpu_new
            time.sleep(3)
            DeviceServiceImpl.write_device_to_cache(device_infos)

    # 动态调度算法，能够扩张和伸缩cpu
    @classmethod
    def cpu_change_ca(cls):
        while cls.num_device == 4:
            device_infos = DeviceMonitor.get_container_info_all()
            while cls.num_task_finished < cls.num_task:
                for tag, device_info in device_infos.items():
                    num_cpu = device_info['Cpu_limit']
                    cpu_new = generate_truncated_normal(num_cpu, 1, num_cpu - 1, num_cpu + 1)
                    # if cpu_new < num_cpu:
                    logging.info(f'update device {tag}')
                    cls.update_container_config(device_info['device_no'], cpu_new)
                    device_infos[tag]['Cpu_limit'] = cpu_new
                time.sleep(3)
                DeviceServiceImpl.write_device_to_cache(device_infos)

    @classmethod
    def avg_delay(cls):
        result_list = {}
        client_ids = DeviceServiceImpl.return_device_list()
        avg_delay = {}
        for client_id in client_ids:
            time_taken = []
            accuracy = []
            result_list_id = DeviceServiceImpl.query_result_by_id(device_id=client_id)
            for result in result_list_id:
                result = result.split(':')
                time_taken.append(float(result[-1]))
                # accuracy.append(result[0])
            result_list[client_id] = time_taken
            avg_delay[client_id] = sum(time_taken) / len(time_taken)
        # 平均任务延迟
        print(result_list)
        logging.info(avg_delay)

    @classmethod
    def utilization_efficiency(cls):
        client_ids = DeviceServiceImpl.return_device_list()
        utilization_efficiency = {}
        for client_id in client_ids:
            cpu_total = 0
            cpu_used = 0
            device_history = DeviceServiceImpl.query_device_history_by_id(client_id, 0)
            for history in device_history:
                # print(json.loads(history))
                history = json.loads(history)
                cpu_total += history['Cpu_limit']
                cpu_used += history['Cpu_limit'] * history['Cpu_perc'] / 100
            utilization_efficiency[client_id] = cpu_used / cpu_total
            logging.info(f'{client_id}: {round(cpu_used / cpu_total * 100, 2)}%')


if __name__ == '__main__':
    # config中修改ip地址
    # 启动redis和docker
    # docker build -t ca .     构建镜像
    # 运行server
    # docker-compose up 启动容器，启动配置在docker-compsoe.yml中
    Server.server(ca=True)
    # Server.utilization_efficiency()
