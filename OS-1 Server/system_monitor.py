import argparse
import os
import signal
import subprocess
import threading
import time

import uvicorn
import yaml
from fastapi import FastAPI, Request

from tools.log import logger


class GpuManager:
    FREE_MEMORY_THRESHOLD = 15 * 1024  # 15GB

    def __init__(self):
        self.update()

    def update(self):
        self.gpu_num = self.get_gpu_num()
        self.gpu_status = self.get_gpu_status()
        self.disabled_gpus = []
        self.free_gpus = []
        # {id: {memory: {total: 0, used: 0, free: 0}, process: [{pid: 0, memory: 0}]}}
        for gpu_id in self.gpu_status:
            free_memory = self.gpu_status[gpu_id]["memory"]["free"]
            if free_memory == 0:
                self.disabled_gpus.append(gpu_id)
            if free_memory > self.FREE_MEMORY_THRESHOLD:
                self.free_gpus.append(gpu_id)

    def get_gpu_num(self):
        return int(subprocess.check_output("nvidia-smi -L | wc -l", shell=True))

    def get_gpu_status(self) -> dict:
        gpu_status = {}
        for i in range(self.gpu_num):
            gpu_status[i] = self.get_gpu_status_by_id(i)
        return gpu_status

    def get_gpu_status_by_id(self, gpu_id) -> dict:
        gpu_status = {}
        gpu_status["id"] = gpu_id
        gpu_status["memory"] = self.get_gpu_memory_by_id(gpu_id)
        gpu_status["process"] = self.get_gpu_process_by_id(gpu_id)
        return gpu_status

    def get_gpu_memory_by_id(self, gpu_id):
        try:
            res = subprocess.check_output(
                "nvidia-smi -i "
                + str(gpu_id)
                + " --query-gpu=memory.total,memory.used,memory.free --format=csv,noheader,nounits",
                shell=True,
            )
            total, used, free = res.decode("utf-8").split(",")
            gpu_memory = {}
            gpu_memory["total"] = int(total)
            gpu_memory["used"] = int(used)
            gpu_memory["free"] = int(free)
        except Exception as e:
            # logger.warning(e)
            gpu_memory = {}
            gpu_memory["total"] = 0
            gpu_memory["used"] = 0
            gpu_memory["free"] = 0
        return gpu_memory

    def get_gpu_process_by_id(self, gpu_id):
        try:
            res = subprocess.check_output(
                "nvidia-smi -i "
                + str(gpu_id)
                + " --query-compute-apps=pid,used_memory --format=csv,noheader,nounits",
                shell=True,
            )
            process_list = res.decode("utf-8").split("\n")
            process_list = [
                process.split(",") for process in process_list if process != ""
            ]
            gpu_process = []
            for process in process_list:
                gpu_process.append({"pid": int(process[0]), "memory": int(process[1])})
        except Exception as e:
            # logger.warning(e)
            gpu_process = []
        return gpu_process

    def get_available_gpus(self):
        self.update()
        if len(self.free_gpus) == 0:
            return None
        available_gpus = []
        for gpu_id in self.free_gpus:
            skip_num = 0
            for i in range(gpu_id):
                if i in self.disabled_gpus:
                    skip_num += 1
            visible_id = gpu_id - skip_num
            available_gpus.append(
                {
                    "gpu_id": gpu_id,
                    "visible_id": visible_id,
                    "free_memory": self.gpu_status[gpu_id]["memory"]["free"],
                }
            )
        available_gpus.sort(key=lambda x: x["free_memory"], reverse=True)
        return available_gpus


class NohupManager:
    def __init__(self, log_dir="log", work_dir="."):
        self.processes = {}
        self.log_dir = log_dir
        self.work_dir = work_dir

    def get_status_dict(self):
        return self.processes

    def start_process(
        self,
        name,
        command,
        work_dir=None,
        conda_env=None,
        log_file_path=None,
        cuda="",
    ):
        try:
            activate_conda = f"conda activate {conda_env} && " if conda_env else ""
            log_file_path = (
                log_file_path if log_file_path else f"{self.log_dir}/{name}.log"
            )
            work_dir = work_dir if work_dir else self.work_dir
            full_command = f"cd {work_dir} && {activate_conda} nohup {command} > {log_file_path} 2>&1 & echo $! > {name}.pid"
            if os.path.exists(f"{name}.pid"):
                os.remove(f"{name}.pid")
            custom_env = os.environ.copy()
            if cuda:
                custom_env["CUDA_VISIBLE_DEVICES"] = cuda
            _ = subprocess.Popen(
                full_command, shell=True, preexec_fn=None, env=custom_env
            )
            while not os.path.exists(f"{name}.pid"):
                time.sleep(0.1)
            with open(f"{name}.pid", "r") as f:
                pid = int(f.read())
            self.processes[name] = pid
            logger.info(
                f"Started process {name} with PID {pid}, log file: {log_file_path}"
            )
            return pid
        except Exception as e:
            logger.info(f"Failed to start process {name}: {str(e)}")
        return 0

    def stop_process(self, name):
        ret_msg = "No such process"
        if name in self.processes:
            try:
                pid = self.processes[name]
                os.kill(pid, signal.SIGKILL)
                del self.processes[name]
                ret_msg = f"Stopped process {name} ({pid})"
                logger.info(ret_msg)
            except Exception as e:
                ret_msg = f"Failed to stop process {name} ({pid}): {str(e)}"
                logger.error(ret_msg)
        return ret_msg


class ModelProcessMonitor:
    def __init__(
        self, config_file="deploy_config.yaml", log_dir="log", work_dir="."
    ) -> None:
        self.gpuManager = GpuManager()
        self.nohupManager = NohupManager(log_dir, work_dir)
        self.module_config = self.load_config(config_file)
        self.gpu_usage = {}  # {gpu_id: module_name}

        self.heart_beat_thread = threading.Thread(
            target=gpu_heartbeat_worker, args=(self,)
        )
        self.heart_beat_thread.daemon = True
        self.heart_beat_thread.start()

    def load_config(self, config_file):
        with open(config_file, "r") as f:
            config = yaml.load(f, Loader=yaml.FullLoader)
        module_config = {}
        for module in config["cuda_modules"]:
            module_config[module["name"]] = module
        return module_config

    def run_module(self, module_name, gpu=None):
        ret_msg = ""
        if module_name in self.gpu_usage.values():
            ret_msg = f"module {module_name} is running"
            logger.info(ret_msg)
            return ret_msg
        if module_name not in self.module_config:
            ret_msg = f"module {module_name} not found"
            logger.error(ret_msg)
            return ret_msg
        module = self.module_config[module_name]
        if gpu is None:
            gpu = self.gpuManager.get_available_gpus()[0]
        if gpu is None:
            ret_msg = "No free GPU"
            logger.info(ret_msg)
            return ret_msg

        cmd = f"{module['command']} "
        cmd += " ".join(module.get("args", []))
        logger.info(f"Start module {module_name} on GPU {gpu['gpu_id']}: {cmd}")
        ret = self.nohupManager.start_process(
            module_name,
            cmd,
            module.get("work_dir", None),
            module.get("conda_env", None),
            module.get("log_file_path", None),
            cuda=f"{gpu['visible_id']}",
        )
        if ret > 0:
            self.gpu_usage[gpu["gpu_id"]] = module_name

        return ret

    def stop_module(self, module_name):
        for gpu_id in self.gpu_usage:
            if self.gpu_usage[gpu_id] == module_name:
                del self.gpu_usage[gpu_id]
                break
        return self.nohupManager.stop_process(module_name)

    def restart_module(self, module_name):
        self.stop_module(module_name)
        return self.run_module(module_name)

    def start_all(self):
        gpulist = self.gpuManager.get_available_gpus()
        logger.info(f"Available GPUs: {gpulist}")
        module_num = len(self.module_config)
        if len(gpulist) < module_num:
            logger.error(
                f"Not enough GPUs, need {module_num}, but only {len(gpulist)} available"
            )
            exit(1)
        for module_name in self.module_config:
            gpu = gpulist.pop()
            self.run_module(module_name, gpu)

    def stop_all(self):
        for module_name in self.module_config:
            self.stop_module(module_name)

    def check_gpu(self):
        self.gpuManager.update()
        disabled_gpus = self.gpuManager.disabled_gpus
        for used_gpu in self.gpu_usage:
            if used_gpu in disabled_gpus:
                module_name = self.gpu_usage[used_gpu]
                logger.error(
                    f"GPU {used_gpu} is disabled, restart module {self.gpu_usage[used_gpu]}"
                )
                self.restart_module(module_name)
                break


def gpu_heartbeat_worker(monitor: ModelProcessMonitor):
    while True:
        time.sleep(15)
        logger.info("Heartbeat")
        monitor.check_gpu()


app = FastAPI()


@app.get("/run/{module_name}")
async def run(module_name):
    return monitor.run_module(module_name)


@app.get("/stop/{module_name}")
async def stop(module_name):
    return monitor.stop_module(module_name)


@app.get("/restart/{module_name}")
async def restart(module_name):
    return monitor.restart_module(module_name)


@app.get("/status")
async def status():
    monitor.gpuManager.update()
    res = {
        "gpu_usage": monitor.gpu_usage,
        "disabled_gpus": monitor.gpuManager.disabled_gpus,
        "free_gpus": monitor.gpuManager.free_gpus,
        "processes": monitor.nohupManager.get_status_dict(),
    }
    return res


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=20000)
    parser.add_argument("--config", type=str, default="deploy_config.yaml")
    parser.add_argument("--log_dir", type=str, default="log")
    parser.add_argument("--work_dir", type=str, default=".")
    parser.add_argument("--start_all", action="store_true", default=False)
    args = parser.parse_args()

    help_msg = f"""
    Usage:
    start module: 
        curl -w '\\n' http://localhost:{args.port}/run/[module_name]
    stop module: 
        curl -w '\\n' http://localhost:{args.port}/stop/[module_name]
    restart module: 
        curl -w '\\n' http://localhost:{args.port}/restart/[module_name]
    show status: 
        curl -w '\\n' http://localhost:{args.port}/status
    """
    logger.warning(help_msg)

    monitor = ModelProcessMonitor(args.config, args.log_dir, args.work_dir)
    if args.start_all:
        monitor.start_all()

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")

    monitor.stop_all()
