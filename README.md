# ArkAnalyzer-HapRay
Code-oriented Performance Analysis for OpenHarmony Apps

## Introduction
ArkAnalyzer-HapRay is a tool designed for performance analysis of OpenHarmony applications. It provides detailed insights into app performance, helping developers optimize their applications for better user experience.

## Documentation
For more detailed information, please refer to the following documents:
- [使用前准备](docs/使用说明.md) - Pre-Use Preparation
- [工具介绍](docs/工具介绍.md) - Tool Introduction
- [收益测试分析](docs/收益测试分析.md) - Performance Test Analysis
- [用例执行预置条件](docs/用例执行预置条件.md) - Test Case Prerequisites

## Build
```
npm install
npm run build
```

## Release
```
npm run release
```

## Usage Guide

### Dependencies
- pip > 23.0.1
- Python 3.9 ~ 3.12, 
- [Command Line Tools for HarmonyOS](https://developer.huawei.com/consumer/cn/download/) > 5.0.5

> ⚠️ Please make sure that the default `python` command in your terminal points to a valid Python interpreter in the 3.9 ~ 3.12 range.
> You can verify this by running:
> ```bash
> python --version
> ```

> ⚠️ When using `pip` to install dependencies, please ensure that your Python package source is reachable from your network.  
> We recommend configuring a mirror (e.g., Tsinghua or Huawei Cloud) if needed.

### Ubuntu System Dependencies
```bash
# Optional: Configure ubuntu-22.04 mirror for faster downloads
sed -i "s@http://.*security.ubuntu.com@http://mirrors.huaweicloud.com@g" /etc/apt/sources.list
sed -i "s@http://.*archive.ubuntu.com@http://mirrors.huaweicloud.com@g" /etc/apt/sources.list

# Optional: Configure ubuntu-24.04 mirror for faster downloads
sed -i "s@http://.*security.ubuntu.com@http://mirrors.huaweicloud.com@g" /etc/apt/sources.list.d/ubuntu.sources
sed -i "s@http://.*archive.ubuntu.com@http://mirrors.huaweicloud.com@g" /etc/apt/sources.list.d/ubuntu.sources

apt-get update && \
apt-get install -y \
    git \
    git-lfs \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev

# Add Command Line Tools for HarmonyOS to PATH
# export command_line_tools=[Command Line Tools for HarmonyOS] directory
export PATH=$PATH:$command_line_tools/tool/node/bin:$command_line_tools/sdk/default/openharmony/toolchains
```
### MacOS Dependencies
```bash
brew install git git-lfs python@3.12

# Add Command Line Tools for HarmonyOS to PATH
# export command_line_tools=[Command Line Tools for HarmonyOS] directory
export PATH=$PATH:$command_line_tools/tool/node/bin:$command_line_tools/sdk/default/openharmony/toolchains
```

### Mac & Linux Installation
```bash
# Initialize environment (only needed once)
git clone https://gitcode.com/SMAT/ArkAnalyzer-HapRay
cd ArkAnalyzer-HapRay/
npm install
npm run build
# Before running tests (make sure you are in the ArkAnalyzer-HapRay directory)
cd perf_testing
source .venv/bin/activate
# Configure test cases in config.yaml as needed. Comment out or delete cases you don't want to run.
python -m scripts.main
```

### Windows Installation
```bash
# Initialize environment (only needed once)
git clone https://gitcode.com/SMAT/ArkAnalyzer-HapRay
cd ArkAnalyzer-HapRay/
npm install
npm run build
# Before running tests (make sure you are in the ArkAnalyzer-HapRay directory)
cd perf_testing
# Command-Line(CMD) Alternative the python virtual environment
.venv\Scripts\activate.bat
# Configure test cases in config.yaml as needed. Comment out or delete cases you don't want to run.
python -m scripts.main
# Examples of optional parameters
python -m scripts.main --so_dir D:\jd\libs\arm64-v8a --run_testcases ResourceUsage_PerformanceDynamic_jingdong_0010 ResourceUsage_PerformanceDynamic_jingdong_0020
# Analyze binary files for optimization flags, supports detection of .hap/.hsp/.so files.
python -m scripts.main -i Directory/File [-jN]
```

## Detailed Explanation of the config.yaml configuration File in perf_testing:

### 1.Preset testcases
```yaml
run_testcases:
 - PerformanceDynamic_com_example_wsywechat_0010
 - ResourceUsage_PerformanceDynamic_xhs_0010
 - ResourceUsage_PerformanceDynamic_xhs_0020
 - ResourceUsage_PerformanceDynamic_xhs_0030
 - ResourceUsage_PerformanceDynamic_xhs_0040
 - ResourceUsage_PerformanceDynamic_xhs_0050
 - ResourceUsage_PerformanceDynamic_xhs_0060
 - ResourceUsage_PerformanceDynamic_xhs_0070
 - ResourceUsage_PerformanceDynamic_bilibili_0010
 - ResourceUsage_PerformanceDynamic_bilibili_0020
 - ResourceUsage_PerformanceDynamic_bilibili_0030
 - ResourceUsage_PerformanceDynamic_bilibili_0040
 - ResourceUsage_PerformanceDynamic_bilibili_0050
 - ResourceUsage_PerformanceDynamic_jingdong_0010
 - ResourceUsage_PerformanceDynamic_jingdong_0020
 - ResourceUsage_PerformanceDynamic_jingdong_0030
 - ResourceUsage_PerformanceDynamic_jingdong_0040
 - ResourceUsage_PerformanceDynamic_jingdong_0050
 - ResourceUsage_PerformanceDynamic_jingdong_0080
 - ResourceUsage_PerformanceDynamic_jingdong_0090
 - ResourceUsage_PerformanceDynamic_jingdong_1000
 - ResourceUsage_PerformanceDynamic_jingdong_0110
 - ResourceUsage_PerformanceDynamic_jingdong_0120
 - ResourceUsage_PerformanceDynamic_zhifubao_0010
 - ResourceUsage_PerformanceDynamic_zhifubao_0020
 - ResourceUsage_PerformanceDynamic_zhifubao_0060
 - ResourceUsage_PerformanceDynamic_zhifubao_0070
 - ResourceUsage_PerformanceDynamic_zhifubao_0080
 - ResourceUsage_PerformanceDynamic_zhifubao_0100
 - ResourceUsage_PerformanceDynamic_Douyin_0010
 - ResourceUsage_PerformanceDynamic_taobao_9999
```

### 2.After setting the so_dir parameter, the import with the symbol so can be supported. This address is the storage path of the.so files in the debug package or the release package
```yaml
so_dir:
  - xxx
```

### 3.If both config.yaml is configured and parameters are passed in the command line, with the parameters passed in the command line being the main one, the two parameters can be merged:
```
  Use case 1 is passed through the command line, and use case 2 is configured in the configuration file. Eventually, both use cases will be executed.
```

## About Flame diagram

### start HiSmartPerf server:

#### third-party/HiSmartPerf_20250109/main.exe
#### third-party/HiSmartPerf_20250109/main_darwin
#### third-party/HiSmartPerf_20250109/main_linux


