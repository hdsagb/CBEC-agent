# 第三方参考项目说明（THIRD-PARTY NOTICES）

本项目（CBEC Agent）在设计与开发过程中参考了以下开源项目。**当前代码库中尚未直接复制任何第三方代码**；凡后续从允许的开源项目中复制或改写代码，必须在对应条目下登记。

参考仓库本地克隆位置：`D:\Users\3257219077\DevEcoStudioProjects\cbec-agent-references\`（不入版本库）。

---

## 一、MIT 许可项目（允许商用与二次开发）

### 1. LabelGou

- 仓库：<https://github.com/su-qihui/LabelGou>
- 许可：MIT License — Copyright (c) 2026 LabelGou
- 参考内容：箱唛字段口径（收发货人、目的港、件数毛重等）与模板布局思路
- 引入状态：**暂未引入代码**（仅阅读学习）

### 2. customs

- 仓库：<https://github.com/logiic-ltd/customs>
- 许可：MIT License（仓库内 `license.txt` 为 MIT 模板，未填写具体版权人行，以仓库声明为准）
- 参考内容：报关数据模型口径（报关单要素字段划分）
- 引入状态：**暂未引入代码**（仅阅读学习）

---

## 二、无 License 项目（仅参考思路，严禁复制代码）

> 以下项目仓库未附带开源许可证，依法保留所有权利。只能阅读、学习其交互与流程思路，**不得复制任何源代码**到本项目。

### 1. -GeneAI-SS26-AI-assisted-procurement-agent

- 仓库：<https://github.com/tianGan11/-GeneAI-SS26-AI-assisted-procurement-agent>
- 许可：无（保留所有权利）
- 仅参考：AI 辅助采购 Agent 的任务编排思路

### 2. shipping-mark-generator

- 仓库：<https://github.com/middlegold9/shipping-mark-generator>
- 许可：无（保留所有权利）
- 仅参考：箱唛生成器的编辑器交互思路

---

## 三、引入登记规范

从上述 MIT 项目复制或改写代码时：

1. 在对应条目下追加「引入清单」：本项目文件路径 ← 原始文件路径 + 原始 commit + 引入日期。
2. 保留原版权声明；实质性修改的文件在文件头注明 `Modified from <repo>`。
3. 本项目对外分发时，随附各 MIT License 全文副本（见附录）。
4. 无 License 项目永远不复制代码；发现已误引入立即删除并替换为原创实现。

---

## 附录：MIT License 副本（LabelGou）

```text
MIT License

Copyright (c) 2026 LabelGou

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
