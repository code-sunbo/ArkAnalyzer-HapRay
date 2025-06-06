/*
 * Copyright (c) 2025 Huawei Device Co., Ltd.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import fs from 'fs';
import path from 'path';
import { Command } from 'commander';
import { DOMParser } from '@xmldom/xmldom';
import Logger, { LOG_MODULE_TYPE } from 'arkanalyzer/lib/utils/logger';
import { getComponentCategories } from '../../core/component';
import { PerfAnalyzer, Step } from '../../core/perf/perf_analyzer';
import { GlobalConfig } from '../../config/types';
import { getConfig, initConfig } from '../../config';
import { traceStreamerCmd } from '../../services/external/trace_streamer';
import { checkPerfAndHtraceFiles, copyDirectory, copyFile, getSceneRoundsFolders } from '../../utils/folder_utils';
import { saveJsonArray } from '../../utils/json_utils';
import { TestSceneInfo } from '../../core/perf/perf_analyzer_base';
import { StepJsonData } from '../../core/perf/perf_data_transformer';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);
const VERSION = '1.0.0';

const DbtoolsCli = new Command('dbtools')
    .requiredOption('-i, --input <string>', 'scene test report path')
    .option('--choose', 'choose one from rounds', false)
    .option('--disable-dbtools', 'disable dbtools', false)
    .option('-s, --soDir <string>', '--So_dir soDir', '')
    .action(async (...args: any[]) => {
        let cliArgs: Partial<GlobalConfig> = { ...args[0] };
        initConfig(cliArgs, (config) => {
            config.choose = args[0].choose;
            config.inDbtools = !args[0].disableDbtools;
        });

        await main(args[0].input);
    });

// 定义 testinfo.json 数据的结构
export interface TestInfo {
    app_id: string;
    app_name: string;
    app_version: string;
    scene: string;
    timestamp: number;
}

export interface SummaryInfo {
    rom_version: string,
    app_version: string,
    scene: string,
    step_name: string,
    step_id: number,
    round: number,
    count: number,
}

export interface ResultInfo {
    rom_version: string;
    device_sn: string;
}

// 定义整个 steps 数组的结构
export type Steps = Step[];

function getPerfDataPaths(inputPath: string, steps: Steps): string[] {
    return steps.map((step) => path.join(inputPath, 'hiperf', `step${step.stepIdx.toString()}`, 'perf.data'));
}

function getPerfDbPaths(inputPath: string, steps: Steps): string[] {
    return steps.map((step) => path.join(inputPath, 'hiperf', `step${step.stepIdx.toString()}`, 'perf.db'));
}

function getHtracePaths(inputPath: string, steps: Steps): string[] {
    return steps.map((step) => path.join(inputPath, 'htrace', `step${step.stepIdx.toString()}`, 'trace.htrace'));
}

// async function main(config: GlobalConfig): Promise<void> {
async function main(input: string): Promise<void> {
    if (getConfig().choose) {//选择轮次并输出json
        logger.info(`Input dir is: ${input}`);
        const roundFolders = getSceneRoundsFolders(input);
        if (roundFolders.length === 0) {
            logger.error(input + '一轮测试信息都没有,无法生成报告！');
            return;
        }
        let output = path.join(input, 'report');
        if (!fs.existsSync(output)) {
            logger.info(`Creating output dir: ${output}`);
            fs.mkdirSync(output, { recursive: true });
        }

        let resultInfo: ResultInfo = { rom_version: '', device_sn: '' };

        //load result.xml
        let resultXml = path.join(roundFolders[0], 'result', path.basename(input) + '.xml');
        if (!fs.existsSync(resultXml)) {
            logger.error('load' + resultXml + ':失败！');
        } else {
            try {
                // 使用 DOMParser 解析 XML字符串
                const parser = new DOMParser();
                const xmlDoc = parser.parseFromString(fs.readFileSync(resultXml, 'utf-8'), 'text/xml');

                // 获取 testsuites 元素
                const testsuitesElement = xmlDoc.getElementsByTagName('testsuites')[0];

                // 提取starttime 属性
                let devicesAttr = testsuitesElement.getAttribute('devices');

                if (!devicesAttr) {
                    logger.error('parse' + resultXml + ':失败！');
                } else {
                    const devices = JSON.parse(
                        devicesAttr
                            .replace(/<!\[CDATA\[(.*?)\]\]>/gs, '$1')
                            .replace(/^\[+/, '')
                            .replace(/]+$/, '')
                            .replace(/\\"/g, '"')
                            .replace(/'/g, '"'));
                    resultInfo.rom_version = devices.version;
                    resultInfo.device_sn = devices.sn;
                }
            } catch (error) {
                logger.error('parse' + resultXml + ':失败！');
            }
        }

        // load testinfo.json
        let testInfoPath = path.join(roundFolders[0], 'testInfo.json')
        await copyFile(testInfoPath, path.join(input, 'testInfo.json'));
        let rawData = fs.readFileSync(testInfoPath, 'utf8');
        const testInfo: TestInfo = JSON.parse(rawData);

        // load steps.json
        let stepsJsonPath = path.join(roundFolders[0], 'hiperf', 'steps.json')
        await copyFile(stepsJsonPath, path.join(input, 'hiperf', 'steps.json'));
        rawData = fs.readFileSync(stepsJsonPath, 'utf8');
        const steps: Steps = JSON.parse(rawData);
        let stepsCollect: StepJsonData[] = [];
        for (let i = 0; i < steps.length; i++) {
            let stepItem: StepJsonData = {
                step_name: steps[i].description,
                step_id: steps[i].stepIdx,
                count: 0,
                round: 0,
                perf_data_path: '',
                data: []
            };
            let result: number[] = [];
            let perfAnalyzer = new PerfAnalyzer('');
            let dbPaths: string[] = [];
            let tracePaths: string[] = [];
            let choose = 0;
            let tracePath = '';
            let dbPath = '';
            if (roundFolders.length >= 3) {
                for (let index = 0; index < roundFolders.length; index++) {
                    const roundFolder = roundFolders[index];

                    tracePath = path.join(roundFolders[index], 'hiperf', `step${steps[i].stepIdx.toString()}`, 'perf.data');
                    dbPath = path.join(roundFolders[index], 'hiperf', `step${steps[i].stepIdx.toString()}`, 'perf.db');
                    if (!fs.existsSync(dbPath)) {
                        traceStreamerCmd(tracePath, dbPath);
                    }
                    dbPaths.push(dbPath);
                    tracePaths.push(tracePath);

                    const sum = await perfAnalyzer.calcPerfDbTotalInstruction(dbPath);
                    result[index] = sum;
                    logger.info(roundFolder + '步骤：' + i + '轮次：' + index + '负载总数:' + sum);
                }
                let total = 0;
                let max = Math.max(...result);
                let min = Math.min(...result);
                result.map((v) => (total += v));
                let avg = (total - max - min) / (result.length - 2);


                let skipMax = false;
                let skipMin = false;
                let diffMin = max;

                for (let idx = 0; idx < result.length; idx++) {
                    const v = result[idx];
                    if (v === max && !skipMax) {
                        skipMax = true;
                        continue;
                    }
                    if (v === min && !skipMin) {
                        skipMin = true;
                        continue;
                    }
                    let diff = Math.abs(v - avg);
                    if (diff < diffMin) {
                        diffMin = diff;
                        choose = idx;
                    }
                }
            } else {
                tracePath = path.join(roundFolders[0], 'hiperf', `step${steps[i].stepIdx.toString()}`, 'perf.data');
                dbPath = path.join(roundFolders[0], 'hiperf', `step${steps[i].stepIdx.toString()}`, 'perf.db');
                if (!fs.existsSync(dbPath)) {
                    traceStreamerCmd(tracePath, dbPath);
                }
                dbPaths.push(dbPath);
                tracePaths.push(tracePath);
                result.push(await perfAnalyzer.calcPerfDbTotalInstruction(dbPath));
            }

            logger.info(dbPaths[choose] + ' : setp' + i + ' select round' + choose + ' .');
            //将hiperf和htrace文件复制到最终目录
            const choosePerfDir = path.join(roundFolders[choose], 'hiperf', `step${steps[i].stepIdx.toString()}`);
            const chooseHtraceDir = path.join(roundFolders[choose], 'htrace', `step${steps[i].stepIdx.toString()}`);
            const chooseResultDir = path.join(roundFolders[choose], 'result');
            const scenePerfDir = path.join(input, 'hiperf', `step${steps[i].stepIdx.toString()}`);
            const sceneHtraceDir = path.join(input, 'htrace', `step${steps[i].stepIdx.toString()}`);
            const ResultDir = path.join(input, 'result');
            await copyDirectory(choosePerfDir, scenePerfDir);
            await copyDirectory(chooseHtraceDir, sceneHtraceDir);
            await copyDirectory(chooseResultDir, ResultDir);
            stepItem.count = result[choose];
            stepItem.round = choose;
            stepItem.perf_data_path = tracePaths[choose];
            stepsCollect.push(stepItem);
        }

        await saveJsonFile(output, resultInfo, testInfo, stepsCollect);
    } else {//输出hiperfjson
        logger.info(`Input dir is: ${input}`);

        let output = path.join(input, 'report');
        let summaryJsonPath = path.join(output, 'summary_info.json');
        if (!fs.existsSync(summaryJsonPath)) {
            logger.error(`${summaryJsonPath}: 文件不存在，说明轮次选择步骤失败，需要重试上一步！`);
            return;
        }
        //load summary_info.json
        let summaryJson = fs.readFileSync(summaryJsonPath, 'utf8');
        const summaryJsons: SummaryInfo[] = JSON.parse(summaryJson);
        let checkResult = await checkPerfAndHtraceFiles(input,summaryJsons.length);
        if(!checkResult){
            logger.error('hiperf数据或者htrace数据不全，需要执行上一步补充！');
            return;
        }
        // load testinfo.json
        let testInfoPath = path.join(input, 'testInfo.json')
        let rawData = fs.readFileSync(testInfoPath, 'utf8');
        const testInfo: TestInfo = JSON.parse(rawData);

        // load steps.json
        let stepsJsonPath = path.join(input, 'hiperf', 'steps.json')
        rawData = fs.readFileSync(stepsJsonPath, 'utf8');
        const steps: Steps = JSON.parse(rawData);
        let perfDataPaths = getPerfDataPaths(input, steps);
        let perfDbPaths = getPerfDbPaths(input, steps);
        let htracePaths = getHtracePaths(input, steps);
        let stepsCollect: StepJsonData[] = [];

        for (let i = 0; i < steps.length; i++) {
            let stepItem: StepJsonData;
            let perfAnalyzer = new PerfAnalyzer('');
            stepItem = await perfAnalyzer.analyze2(perfDbPaths[i], testInfo.app_id, steps[i]);
            let testSceneInfo: TestSceneInfo = { packageName: testInfo.app_id, scene: testInfo.scene, osVersion: summaryJsons[i].rom_version, timestamp: testInfo.timestamp };
            await perfAnalyzer.analyze(perfDbPaths[i], testSceneInfo, output, steps[i].stepIdx);
            stepItem.round = summaryJsons[i].round;
            stepItem.perf_data_path = perfDbPaths[i];
            stepsCollect.push(stepItem);
        }
        await saveHiperfJson(output, summaryJsons[0], testInfo, perfDataPaths, perfDbPaths, htracePaths, stepsCollect);
    }

}

async function saveJsonFile(output: string, resultInfo: ResultInfo, testInfo: TestInfo, steps: StepJsonData[]): Promise<void> {
    let summaryJsonObject: SummaryInfo[] = []
    steps.forEach(step => {
        const summaryObject: SummaryInfo = {
            rom_version: resultInfo.rom_version,
            app_version: testInfo.app_version,
            scene: testInfo.scene,
            step_name: step.step_name,
            step_id: step.step_id,
            round: step.round,
            count: step.count
        }
        summaryJsonObject.push(summaryObject);
    })
    await saveJsonArray(summaryJsonObject, path.join(output, 'summary_info.json'));
}

async function saveHiperfJson(output: string, summaryInfo: SummaryInfo, testInfo: TestInfo, perfDataPaths: string[], perfDbPaths: string[], htracePaths: string[], steps: StepJsonData[]): Promise<void> {
    output = path.join(output,'../','hiperf');
    const jsonObject = {
        rom_version: summaryInfo.rom_version,
        app_id: testInfo.app_id,
        app_name: testInfo.app_name,
        app_version: testInfo.app_version,
        scene: testInfo.scene,
        timestamp: testInfo.timestamp,
        perfDataPath: perfDataPaths,
        perfDbPath: perfDbPaths,
        htracePath: htracePaths,
        categories: getComponentCategories()
            .filter((category) => category.id >= 0)
            .map((category) => category.name),
        steps: steps,
    };
    await saveJsonArray([jsonObject], path.join(output, 'hiperf_info.json'));
}

export const HaprayCli = new Command('hapray').version(VERSION).addCommand(DbtoolsCli);
