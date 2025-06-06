import json
import logging
import os
import subprocess
import threading
import time
from abc import abstractmethod

from devicetest.core.test_case import TestCase
from xdevice import platform_logger
from hypium import UiDriver

from hapray.core.common.CommonUtils import CommonUtils
from hapray.core.common.FrameAnalyzer import FrameAnalyzer
from hapray.core.config.config import Config
from hapray.core.common.FrameAnalyzer import FrameAnalyzer

Log = platform_logger("PerfTestCase")


class PerfTestCase(TestCase):
    def __init__(self, tag: str, configs):
        super().__init__(tag, configs)
        self.driver = UiDriver(self.device1)
        self.TAG = tag
        self.pid = -1

    @property
    @abstractmethod
    def steps(self) -> []:
        pass

    @property
    @abstractmethod
    def app_package(self) -> str:
        pass

    @property
    @abstractmethod
    def app_name(self) -> str:
        pass

    @property
    def report_path(self) -> str:
        return self.get_case_report_path()

    @staticmethod
    def _get_hiperf_cmd(pid, output_path, duration, sample_all=False):
        """生成 hiperf 命令

        Args:
            pid: 进程ID
            output_path: 输出文件路径
            duration: 采集持续时间（秒）
            sample_all: 是否采样所有进程（需要root权限）

        Returns:
            str: 完整的 hiperf 命令
        """
        if sample_all:
            cmd = f"hiperf record -a --call-stack dwarf --kernel-callchain -f 1000 --cpu-limit 100 -e raw-instruction-retired --enable-debuginfo-symbolic --clockid boottime -m 1024 -d {duration} -o {output_path}"
        else:
            cmd = f"hiperf record -p {pid} --call-stack dwarf --kernel-callchain -f 1000 --cpu-limit 100 -e raw-instruction-retired --enable-debuginfo-symbolic --clockid boottime -m 1024 -d {duration} -o {output_path}"
        return cmd

    @staticmethod
    def _get_trace_and_perf_cmd(pid, output_path, duration, sample_all=False):
        """生成同时抓取trace和perf数据的命令

        Args:
            pid: 进程ID
            output_path: 输出文件路径
            duration: 采集持续时间（秒）
            sample_all: 是否采样所有进程（需要root权限）

        Returns:
            str: 完整的命令
        """
        if sample_all:
            recort_args = f"-a --call-stack dwarf --kernel-callchain -f 1000 --cpu-limit 100 -e raw-instruction-retired --enable-debuginfo-symbolic --clockid boottime -m 1024 -d {duration}"
        else:
            recort_args = f"-p {pid} --call-stack dwarf --kernel-callchain -f 1000 --cpu-limit 100 -e raw-instruction-retired --enable-debuginfo-symbolic --clockid boottime -m 1024 -d {duration}"
        # 基础命令部分
        cmd = f"""hiprofiler_cmd \\
  -c - \\
  -o {output_path}.htrace \\
  -t {duration} \\
  -s \\
  -k \\
<<CONFIG
# 会话配置
 request_id: 1
 session_config {{
  buffers {{
   pages: 16384
  }}
 }}

# ftrace插件配置
 plugin_configs {{
  plugin_name: "ftrace-plugin"
  sample_interval: 1000
  config_data {{
   # ftrace事件配置
   ftrace_events: "sched/sched_switch"
   ftrace_events: "power/suspend_resume"
   ftrace_events: "sched/sched_wakeup"
   ftrace_events: "sched/sched_wakeup_new"
   ftrace_events: "sched/sched_waking"
   ftrace_events: "sched/sched_process_exit"
   ftrace_events: "sched/sched_process_free"
   ftrace_events: "task/task_newtask"
   ftrace_events: "task/task_rename"
   ftrace_events: "power/cpu_frequency"
   ftrace_events: "power/cpu_idle"

   # hitrace类别配置
   hitrace_categories: "ability"
   hitrace_categories: "ace"
   hitrace_categories: "app"
   hitrace_categories: "ark"
   hitrace_categories: "binder"
   hitrace_categories: "disk"
   hitrace_categories: "freq"
   hitrace_categories: "graphic"
   hitrace_categories: "idle"
   hitrace_categories: "irq"
   hitrace_categories: "memreclaim"
   hitrace_categories: "mmc"
   hitrace_categories: "multimodalinput"
   hitrace_categories: "notification"
   hitrace_categories: "ohos"
   hitrace_categories: "pagecache"
   hitrace_categories: "rpc"
   hitrace_categories: "sched"
   hitrace_categories: "sync"
   hitrace_categories: "window"
   hitrace_categories: "workq"
   hitrace_categories: "zaudio"
   hitrace_categories: "zcamera"
   hitrace_categories: "zimage"
   hitrace_categories: "zmedia"

   # 缓冲区配置
   buffer_size_kb: 204800
   flush_interval_ms: 1000
   flush_threshold_kb: 4096
   parse_ksyms: true
   clock: "boot"
   trace_period_ms: 200
   debug_on: false
  }}
 }}

# hiperf插件配置
 plugin_configs {{
  plugin_name: "hiperf-plugin"
  sample_interval: 5000
  config_data {{
   is_root: false
   outfile_name: "{output_path}"
   record_args: "{recort_args}"
  }}
 }}
CONFIG"""
        return cmd

    @staticmethod
    def _get_trace_and_perf_cmd_multi(pids, output_path, duration):
        """生成同时抓取多个进程的trace和perf数据的命令

        Args:
            pids: 进程ID列表，不能为空
            output_path: 输出文件路径
            duration: 采集持续时间（秒）

        Returns:
            str: 完整的命令
        """
        pid_args = ','.join(map(str, pids))
        recort_args = f"-p {pid_args} --call-stack dwarf --kernel-callchain -f 1000 --cpu-limit 100 -e raw-instruction-retired --enable-debuginfo-symbolic --clockid boottime -m 1024 -d {duration}"
        # 基础命令部分
        cmd = f"""hiprofiler_cmd \\
  -c - \\
  -o {output_path}.htrace \\
  -t {duration} \\
  -s \\
  -k \\
<<CONFIG
# 会话配置
 request_id: 1
 session_config {{
  buffers {{
   pages: 16384
  }}
 }}

# ftrace插件配置
 plugin_configs {{
  plugin_name: "ftrace-plugin"
  sample_interval: 1000
  config_data {{
   # ftrace事件配置
   ftrace_events: "sched/sched_switch"
   ftrace_events: "power/suspend_resume"
   ftrace_events: "sched/sched_wakeup"
   ftrace_events: "sched/sched_wakeup_new"
   ftrace_events: "sched/sched_waking"
   ftrace_events: "sched/sched_process_exit"
   ftrace_events: "sched/sched_process_free"
   ftrace_events: "task/task_newtask"
   ftrace_events: "task/task_rename"
   ftrace_events: "power/cpu_frequency"
   ftrace_events: "power/cpu_idle"

   # hitrace类别配置
   hitrace_categories: "ability"
   hitrace_categories: "ace"
   hitrace_categories: "app"
   hitrace_categories: "ark"
   hitrace_categories: "binder"
   hitrace_categories: "disk"
   hitrace_categories: "freq"
   hitrace_categories: "graphic"
   hitrace_categories: "idle"
   hitrace_categories: "irq"
   hitrace_categories: "memreclaim"
   hitrace_categories: "mmc"
   hitrace_categories: "multimodalinput"
   hitrace_categories: "notification"
   hitrace_categories: "ohos"
   hitrace_categories: "pagecache"
   hitrace_categories: "rpc"
   hitrace_categories: "sched"
   hitrace_categories: "sync"
   hitrace_categories: "window"
   hitrace_categories: "workq"
   hitrace_categories: "zaudio"
   hitrace_categories: "zcamera"
   hitrace_categories: "zimage"
   hitrace_categories: "zmedia"

   # 缓冲区配置
   buffer_size_kb: 204800
   flush_interval_ms: 1000
   flush_threshold_kb: 4096
   parse_ksyms: true
   clock: "boot"
   trace_period_ms: 200
   debug_on: false
  }}
 }}

# hiperf插件配置
 plugin_configs {{
  plugin_name: "hiperf-plugin"
  debug_on: false
  config_data {{
   is_root: false
   outfile_name: "{output_path}"
   record_args: "{recort_args}"
  }}
 }}
CONFIG"""
        return cmd

    @staticmethod
    def _run_hiperf(driver, cmd):
        """在后台线程中运行 hiperf 命令"""
        driver.shell(cmd, timeout=120)

    @staticmethod
    def generate_hapray_report(scene_dirs: list[str], scene_dir: str, so_dir: str) -> bool:
        """
        执行 hapray 命令生成性能分析报告
        :param scene_dir: 场景目录路径，例如 perf_output/wechat002 或完整路径
        :return: bool 表示是否成功生成报告
        Log日志和具体case相关，生成报告时已与case无关，导致Log无法落盘，此处使用logging记录日志
        """

        if not scene_dirs:
            logging.error("Error: scene_dirs length is 0!")
            return False

        # 获取 perf_testing 目录
        perf_testing_dir = CommonUtils.get_project_root()

        # 获取项目根目录（perf_testing 的上一级目录）
        project_root = os.path.dirname(perf_testing_dir)

        # 检查是否已经是完整路径
        if os.path.isabs(scene_dir):
            # 如果是绝对路径，直接使用
            full_scene_dir = scene_dir
        else:
            # 否则，添加 perf_testing 目录前缀
            full_scene_dir = os.path.normpath(os.path.join(perf_testing_dir, scene_dir))

        # 获取 hapray-cmd.js 的绝对路径
        hapray_cmd_path = os.path.abspath(os.path.join(perf_testing_dir, 'hapray-toolbox', 'hapray-cmd.js'))

        # 检查 hapray-cmd.js 是否存在
        if not os.path.exists(hapray_cmd_path):
            logging.error(f"Error: hapray-cmd.js not found at {hapray_cmd_path}")
            return False

        # 打印调试信息
        logging.info(f"Project root: {project_root}")
        logging.info(f"Scene directory: {full_scene_dir}")
        logging.info(f"Hapray command path: {hapray_cmd_path}")
        logging.info(f"Current working directory: {os.getcwd()}")

        # 确保路径使用双反斜杠
        full_scene_dir_escaped = full_scene_dir.replace('\\', '\\\\')
        hapray_cmd_path_escaped = hapray_cmd_path.replace('\\', '\\\\')

        # 构建并执行命令 - 使用绝对路径
        cmd = [
            'node', hapray_cmd_path_escaped,
            'hapray', 'dbtools',
            '--choose', 'true',
            '-i', full_scene_dir_escaped
        ]

        # 打印完整命令
        logging.info(f"Executing command: {' '.join(cmd)}")

        # 轮次选择 信息记录在report目录下的summary_info.json中。
        if PerfTestCase.exe_hapray_cmd(cmd, project_root):
            logging.info("轮次选择成功！信息记录在report目录下的summary_info.json中。")
        else:
            logging.info("轮次选择失败！")
            return False
        # hiperf分析，生成hiperf/hiperf_info.json
        if so_dir == None:
            cmd = [
                'node', hapray_cmd_path_escaped,
                'hapray', 'dbtools',
                '-i', full_scene_dir_escaped
            ]
        else:
            cmd = [
                'node', hapray_cmd_path_escaped,
                'hapray', 'dbtools',
                '-i', full_scene_dir_escaped,
                '-s', so_dir
            ]
        # 打印完整命令
        logging.info(f"Executing command: {' '.join(cmd)}")
        if PerfTestCase.exe_hapray_cmd(cmd, project_root):
            logging.info("hiperf分析成功！信息记录在hiperf目录下的hiperf_info.json中。")
        else:
            logging.info("hiperf分析失败失败！")
            return False
        # 在所有报告生成完成后进行卡顿帧分析
        logging.info(f"Starting frame drops analysis for {scene_dir}...")
        if FrameAnalyzer.analyze_frame_drops(scene_dir):
            logging.info(f"Successfully analyzed frame drops for {scene_dir}")
        else:
            logging.error(f"Failed to analyze frame drops for {scene_dir}")
        perf_json_path = os.path.join(scene_dir, 'hiperf', 'hiperf_info.json')
        trace_json_path = os.path.join(scene_dir, 'htrace', 'frame_analysis_summary.json')
        html_path = os.path.join(perf_testing_dir, 'hapray-toolbox', 'res', 'report_template.html')
        output_path = os.path.join(scene_dir, 'report', 'hapray_report.html')
        PerfTestCase.create_html(perf_json_path, trace_json_path, html_path, output_path)
        return True

    @staticmethod
    def create_html(perf_json_path: str, trace_json_path: str, html_path: str, output_path: str):
        # 注入perf信息
        PerfTestCase.replace_html_with_json(perf_json_path, 'JSON_DATA_PLACEHOLDER', html_path, output_path)
        # 注入trace信息
        PerfTestCase.replace_html_with_json(trace_json_path, 'FRAME_JSON_PLACEHOLDER', output_path, output_path)
        return

    @staticmethod
    def replace_html_with_json(json_path: str, replace_str: str, html_path: str, output_path: str) -> None:
        """
        读取JSON数组文件，用第一个元素替换HTML中的占位符

        Args:
            json_path: JSON文件路径
            html_path: HTML模板文件路径
            output_path: 输出文件路径
        """
        try:
            # 验证输入文件是否存在
            for file_path in [json_path, html_path]:
                if not os.path.exists(file_path):
                    raise FileNotFoundError(f"文件不存在: {file_path}")

            # 读取并解析JSON文件
            with open(json_path, 'r', encoding='utf-8') as f:
                try:
                    json_data = json.load(f)
                except json.JSONDecodeError as e:
                    raise ValueError(f"JSON解析错误: {e}")

            # 验证JSON结构
            if not isinstance(json_data, list) or len(json_data) == 0:
                raise ValueError("JSON文件必须包含非空数组")

            # 转换为格式化的JSON字符串（保留中文）
            if replace_str == 'JSON_DATA_PLACEHOLDER':
                first_obj = json.dumps(json_data[0], indent=2, ensure_ascii=False)
            else:
                first_obj = json.dumps(json_data, indent=2, ensure_ascii=False)
            # 读取HTML文件
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()

            new_html = html_content.replace(replace_str, first_obj)

            # 写入输出文件（自动创建目录）
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(new_html)

            logging.error(f"替换完成，结果已保存至 {output_path}")

        except FileNotFoundError as e:
            logging.error(f"错误: {e}")
        except ValueError as e:
            logging.error(f"错误: {e}")
        except PermissionError:
            logging.error(f"错误: 没有权限访问文件或目录")
        except Exception as e:
            logging.error(f"意外错误: {e}")

    @staticmethod
    def exe_hapray_cmd(cmd, project_root):
        try:
            # 设置工作目录为项目根目录，并指定编码为 utf-8
            result = subprocess.run(
                cmd,
                check=True,
                cwd=project_root,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'  # 使用 replace 策略处理无法解码的字符
            )
            logging.info(f"Command output: {result.stdout}")
            if result.stderr:
                logging.error(f"Command stderr: {result.stderr}")
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to generate HapRay report: {str(e)}")
            if e.stdout:
                logging.error(f"Command stdout: {e.stdout}")
            if e.stderr:
                logging.error(f"Command stderr: {e.stderr}")
            return False
        except FileNotFoundError:
            logging.error(
                "Error: Node.js command not found. Please make sure Node.js is installed and in your PATH.")
            return False

    def make_reports(self):
        # 读取配置文件中的步骤信息
        steps_info = []
        for i, step in enumerate(self.steps, 1):
            steps_info.append({
                "name": step['name'],
                "description": step['description'],
                "stepIdx": i
            })

        # 保存步骤信息到steps.json
        steps_json_path = os.path.join(self.report_path, 'hiperf/steps.json')

        with open(steps_json_path, 'w', encoding='utf-8') as f:
            json.dump(steps_info, f, ensure_ascii=False, indent=4)

        # 保存测试信息
        self._save_test_info()

    def _save_perf_data(self, device_file, step_id):
        """保存性能数据"""

        # 构建完整的目录结构
        hiperf_dir = os.path.join(self.report_path, 'hiperf')
        step_dir = os.path.join(hiperf_dir, f'step{str(step_id)}')

        # 构建文件路径
        local_output_path = os.path.join(step_dir, Config.get('hiperf.data_filename', 'perf.data'))
        local_output_db_path = os.path.join(step_dir, Config.get('hiperf.db_filename', 'perf.db'))

        # 确保所有必要的目录都存在
        os.makedirs(step_dir, exist_ok=True)

        # 检查设备上的文件是否存在
        try:
            # 使用 ls 命令检查文件是否存在
            result = self.driver.shell(f"ls -l {device_file}")

            if "No such file" in result:
                # 尝试列出目录内容以进行调试
                dir_path = os.path.dirname(device_file)
                self.driver.shell(f"ls -l {dir_path}")
                return

            # 如果文件存在，尝试拉取
            self.driver.pull_file(device_file, local_output_path)

            # 检查本地文件是否成功拉取
            if not os.path.exists(local_output_path):
                return

            # 检查转换后的文件是否存在
            # if not os.path.exists(local_output_db_path):
            #     return

        except Exception as e:
            # 尝试获取更多调试信息
            self.driver.shell("df -h")
            self.driver.shell("ls -l /data/local/tmp/")

    def _save_perf_and_htrace_data(self, device_file, step_id):
        """保存性能数据和htrace数据

        Args:
            device_file: 设备上的perf文件路径
            step_id: 步骤ID
        """
        # 构建perf的目录结构
        hiperf_dir = os.path.join(self.report_path, 'hiperf')
        perf_step_dir = os.path.join(hiperf_dir, f'step{str(step_id)}')

        # 构建htrace的目录结构
        htrace_dir = os.path.join(self.report_path, 'htrace')
        htrace_step_dir = os.path.join(htrace_dir, f'step{str(step_id)}')

        # 构建文件路径
        local_perf_path = os.path.join(perf_step_dir, Config.get('hiperf.data_filename', 'perf.data'))
        local_perf_db_path = os.path.join(perf_step_dir, Config.get('hiperf.db_filename', 'perf.db'))
        local_htrace_path = os.path.join(htrace_step_dir, 'trace.htrace')

        # 确保所有必要的目录都存在
        os.makedirs(perf_step_dir, exist_ok=True)
        os.makedirs(htrace_step_dir, exist_ok=True)

        # 检查设备上的perf文件是否存在
        try:
            perf_result = self.driver.shell(f"ls -l {device_file}")
            if "No such file" in perf_result:
                Log.error(f"Perf file not found: {device_file}")
                return

            # 检查设备上的htrace文件是否存在
            device_htrace_file = f"{device_file}.htrace"
            htrace_result = self.driver.shell(f"ls -l {device_htrace_file}")
            if "No such file" in htrace_result:
                Log.error(f"Htrace file not found: {device_htrace_file}")
                return

            # 拉取perf文件
            self.driver.pull_file(device_file, local_perf_path)
            if not os.path.exists(local_perf_path):
                Log.error(f"Failed to pull perf file to: {local_perf_path}")
                return

            # 拉取htrace文件
            self.driver.pull_file(device_htrace_file, local_htrace_path)
            if not os.path.exists(local_htrace_path):
                Log.error(f"Failed to pull htrace file to: {local_htrace_path}")
                return

            Log.info(f"Successfully saved perf and htrace data for step {step_id}")
            Log.info(f"Perf data saved to: {local_perf_path}")
            Log.info(f"Htrace data saved to: {local_htrace_path}")

        except Exception as e:
            Log.error(f"Error saving perf and htrace data: {str(e)}")
            # 尝试获取更多调试信息
            self.driver.shell("df -h")
            self.driver.shell("ls -l /data/local/tmp/")

    def execute_step_with_perf(self, step_id, action_func, duration):
        """
        执行一个步骤并收集性能数据

        Args:
            step_id: 步骤ID
            action_func: 要执行的动作函数
            duration: 性能数据采集持续时间（秒）
        """
        # 设置当前步骤的输出路径
        output_file = f"/data/local/tmp/hiperf_step{step_id}.data"

        # 确保设备上的目标目录存在
        output_dir = os.path.dirname(output_file)
        self.driver.shell(f"mkdir -p {output_dir}")

        # 清理可能存在的旧文件
        self.driver.shell(f"rm -f {output_file}")

        if self.pid == -1:
            self.pid = self._get_app_pid()

        Log.info(f'execute_step_with_perf thread start run {duration}s')
        # 创建并启动 hiperf 线程
        hiperf_cmd = PerfTestCase._get_hiperf_cmd(self.pid, output_file, duration)
        hiperf_thread = threading.Thread(target=PerfTestCase._run_hiperf, args=(self.driver, hiperf_cmd))
        hiperf_thread.start()

        # 执行动作
        action_func(self.driver)

        # 等待 hiperf 线程完成
        hiperf_thread.join()
        Log.info(f'execute_step_with_perf thread end')

        # 保存性能数据和htrace数据
        self._save_perf_data(output_file, step_id)

    def execute_step_with_perf_and_trace(self, step_id, action_func, duration, sample_all=False, is_multi_pid=True):
        """
        执行一个步骤并同时收集性能数据和trace数据

        Args:
            step_id: 步骤ID
            action_func: 要执行的动作函数
            duration: 数据采集持续时间（秒）
            sample_all: 是否采样所有进程（需要root权限）
            is_multi_pid: 是否采集多个进程的数据，默认为True
        """
        import threading
        # 设置当前步骤的输出路径
        output_file = f"/data/local/tmp/hiperf_step{step_id}.data"

        # 确保设备上的目标目录存在
        output_dir = os.path.dirname(output_file)
        self.driver.shell(f"mkdir -p {output_dir}")

        # 清理可能存在的旧文件
        self.driver.shell(f"rm -f {output_file}")
        self.driver.shell(f"rm -f {output_file}.htrace")

        if self.pid == -1:
            self.pid = self._get_app_pid()

        Log.info(f'execute_step_with_perf_and_trace thread start run {duration}s')

        # 启动采集线程
        if sample_all:
            # 如果是root权限，直接使用sample_all模式
            cmd = PerfTestCase._get_trace_and_perf_cmd(self.pid, output_file, duration, sample_all=True)
        elif is_multi_pid:
            # 如果不是root权限，且需要采集多个进程
            pids, process_names = self._get_app_pids()
            if not pids:
                Log.error("No process found for multi-pid collection")
                return
            # 记录进程信息
            for pid, name in zip(pids, process_names):
                Log.info(f"Found process: {name} (PID: {pid})")
            cmd = PerfTestCase._get_trace_and_perf_cmd_multi(pids, output_file, duration)
        else:
            # 如果不是root权限，且只需要采集单个进程
            cmd = PerfTestCase._get_trace_and_perf_cmd(self.pid, output_file, duration, sample_all=False)

        perf_trace_thread = threading.Thread(target=PerfTestCase._run_hiperf, args=(self.driver, cmd))
        perf_trace_thread.start()

        # 执行动作
        action_func(self.driver)

        # 等待线程完成
        perf_trace_thread.join()
        Log.info(f'execute_step_with_perf_and_trace thread end')

        # 保存性能数据和htrace数据（异步）
        def save_data_async():
            self._save_perf_and_htrace_data(output_file, step_id)

        save_thread = threading.Thread(target=save_data_async)
        save_thread.start()
        # 不等待 save_thread，主流程直接返回

    def _save_test_info(self):
        """
        生成并保存测试信息到testInfo.json
        :return: 保存的结果字典
        """
        # 确保输出目录存在
        os.makedirs(self.report_path, exist_ok=True)

        # 从配置中获取应用名称，如果没有配置则自动获取
        app_version = self._get_app_version()

        # 准备结果信息
        result = {
            "app_id": self.app_package,
            "app_name": self.app_name,
            "app_version": app_version,
            "scene": self.TAG,
            "timestamp": int(time.time() * 1000)  # 毫秒级时间戳
        }

        # 保存到文件
        result_path = os.path.join(self.report_path, 'testInfo.json')
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=4, ensure_ascii=False)

        return result

    def _get_app_version(self) -> str:
        """
        获取应用版本号
        :return: str: 应用版本号
        """
        # 使用 bm dump 命令获取版本号
        cmd = f"bm dump -n {self.app_package}"
        result = self.driver.shell(cmd)
        Log.debug(f"Debug - bm dump result: {result}")  # 添加调试输出

        try:
            # 解析 JSON 结果
            # 移除开头的包名和冒号
            json_str = result.split(':', 1)[1].strip()
            data = json.loads(json_str)

            if 'applicationInfo' in data and 'versionName' in data['applicationInfo']:
                version = data['applicationInfo']['versionName']
                if version:
                    Log.debug(f"Debug - Found version: {version}")  # 添加调试输出
                    return version
        except json.JSONDecodeError as e:
            Log.debug(f"Debug - JSON parsing error: {e}")  # 添加调试输出

        Log.debug(f"Debug - No version found for {self.app_package}")  # 添加调试输出
        return "Unknown Version"  # 如果无法获取版本号，返回未知版本

    def _get_app_pids(self) -> tuple[list[int], list[str]]:
        """获取应用的所有相关进程ID和进程名

        使用 ps -ef | grep 命令获取所有相关进程，并过滤掉grep进程本身。
        例如对于 com.jd.hm.mall 可能会返回:
        - PIDs: [1234, 1235]
        - 进程名: ["com.jd.hm.mall", "com.jd.hm.mall:render"]
        等所有相关进程的PID和进程名

        Returns:
            tuple[list[int], list[str]]: 返回两个列表，第一个是进程ID列表，第二个是进程名列表
        """
        # 使用 ps -ef | grep 命令获取所有相关进程
        cmd = f"ps -ef | grep {self.app_package}"
        result = self.driver.shell(cmd)

        # 解析输出，提取PID和进程名
        pids = []
        process_names = []
        for line in result.splitlines():
            # 跳过grep进程本身
            if 'grep' in line:
                continue

            # 尝试从每行提取PID和进程名
            try:
                # ps -ef 输出格式: UID PID PPID ... CMD
                parts = line.split()
                if len(parts) >= 2:
                    pid = int(parts[1])
                    # 获取进程名（通常是最后一个部分）
                    process_name = parts[-1]
                    pids.append(pid)
                    process_names.append(process_name)
            except (ValueError, IndexError):
                continue

        return pids, process_names

    def _get_app_pid(self) -> int:
        pid_cmd = f"pidof {self.app_package}"
        return int(self.driver.shell(pid_cmd).strip())
