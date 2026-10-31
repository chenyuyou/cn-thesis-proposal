# cn-thesis-proposal

**版本：v0.1.0 · 早期测试版**

中文高校本硕博开题报告的研究设计与教学指导 Skill。首版面向经管与社会科学，支持指导撰写、只读审阅、授权修改、Word范文与配套评阅说明、语言润色。方法包涵盖面板因果、问卷实验、案例质性和应用诊断；其他研究类型需要针对性扩展。

## 安装与使用

适用于支持 Agent Skills 格式的 Pi 环境。确认目标路径不存在后，可将仓库克隆到用户技能目录：

```sh
mkdir -p ~/.pi/agent/skills
git clone https://github.com/chenyuyou/cn-thesis-proposal.git ~/.pi/agent/skills/cn-thesis-proposal
```

已有同名目录时，请先备份或比较，不要直接覆盖。运行 `/reload` 后使用 `/skill:cn-thesis-proposal`；如自动触发不稳定，可明确调用。运行所在环境有更高优先级的工具及数据保护规则时，以该环境要求为准。

模板输入：用户提供学校原表和要求；先只读识别并与用户确认目标单元格，不承诺任意学校模板均可自动填充。旧版 .doc、复杂修订、签章和嵌套结构需专门检查。若要检查 .docx 的部分结构，运行：

```sh
python3 scripts/inspect_docx.py /path/to/proposal.docx
python3 -m unittest discover -s tests -v
```

检查脚本不写入源文件，只覆盖ZIP/XML与部分结构特征；不校验引文正确性、不识别全部审批栏、不判断学术质量或视觉分页。模型写作、模板填充和PDF解析由当前环境中的适用技能与工具承担。

## 当前状态与限制

首版不内置任何学校表格、学生报告、论文PDF、图片或本项目的私有范文。问卷、案例和政策设计的单次模型测试发现过事实边界与统计建议问题，已据此调整；双文件生成测试因调用超时及PDF中文缺字而**未通过最终验收**。详细覆盖范围和未完成事项见 [TESTING.md](TESTING.md)。复杂学校表格的安全写入尚未实现或测试。

本仓库尚未指定开源许可证；公开可见不等于授予复制、修改或再分发许可。后续扩充范文、素材及依赖前，应按 [发布检查清单](references/release-checklist.md) 核查权利、隐私和可复现性。
