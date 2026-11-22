# endfield-theme

终末地风格 WebUI 主题：L2 注入式设计语言覆盖，accent / paper / density 三个开关可配置。

## 功能

- 往 dashboard 的 `index.html` 注入受控样式块与字体链接，不改 JS 构建产物；
  dashboard 升级后重新注入即可，卸载/停用自动还原官方外观。
- 设计语法：单一强调色只做填充（当前位置/可点击/醒目提醒）、切角=可点击、
  圆角/阴影/毛玻璃全零、1px 细线分区、宽体大写英文 + 粗体中文、
  侧栏深色命令栏、短硬机械动效、红色只给删除。
- 明暗两套完整主题，跟随 WebUI 自身深浅色设置。
- 等高线底纹：主区右上/左下两角各一片（墨色 18%，不闭合），随明暗自动适配。
- 机械动效：对话框通电展开、提示条擦入擦掉、浮层通电、标签页逐行亮起、
  表格行右移+左色条、开关/分段 280ms 硬停；系统「减少动态效果」时全静止。
- Saira 可变字体自托管（SIL OFL 1.1，许可证随附），中文落 Noto Sans SC / 微软雅黑。

## 安装

1. 将整个 `endfield-theme/` 目录复制到 MaiBot 安装目录的 `plugins/` 下。
2. **完整重启 MaiBot**（热重载不生效），观察加载日志 `[endfield-theme] 主题已注入`。
3. 刷新 WebUI 页面即可看到主题。

## 配置

| 配置节 | 字段 | 默认值 | 说明 |
|---|---|---|---|
| `[plugin]` | `enabled` | `true` | 是否启用主题（关闭即移除注入，恢复官方外观） |
| `[plugin]` | `config_version` | `0.2.1` | 配置版本，升级时触发归一化重建 |
| `[appearance]` | `accent` | `lime` | 强调色：yellow(标准黄) / lime(青柠) / ice(冰蓝) / amber(琥珀) |
| `[appearance]` | `paper` | `neutral` | 纸色：neutral(中性灰白) / warm(暖米色) / cool(冷青灰) |
| `[appearance]` | `density` | `compact` | 密度：compact(紧凑) / standard(标准) / roomy(宽松) |

三个外观开关在 WebUI 插件配置页调整，保存后即时重注入，刷新页面生效。
配置页标签与下拉选项均为中文（zh-CN，另附 en-US 对照）；配置值本身保持英文枚举。
`config.toml` 由 Runner 自动生成，不要手工提交；写入时不能带 UTF-8 BOM。

## 命令 / 工具

无（纯注入式主题插件，不注册 Command / Tool / Hook）。

## 权限与能力

manifest `capabilities` 声明：`declarative_basic`（WebUI 配置页基础声明能力）。
不调用任何消息/LLM 能力，不产生网络请求。

改动 capabilities 后**必须完整重启 MaiBot**（热重载不生效）。

## 故障排查

| 现象 | 原因与处置 |
|---|---|
| 刷新后仍是官方外观 | 未完整重启 MaiBot；或浏览器缓存，强制刷新（Ctrl+F5） |
| 日志「找不到 dashboard 的 index.html」 | maibot-dashboard 资源包未安装，按主程序提示安装 |
| 日志「无法定位 dashboard dist」 | 同上，或 dashboard 包损坏 |
| 字体没变化 | Saira 只覆盖拉丁字符，中文本来就是黑体；检查 dist/fonts/endfield/ 是否有 Saira.ttf |
| 想恢复官方外观 | 配置页关闭 enabled，或卸载插件（自动还原 index.html 并清理字体） |
| dashboard 升级后样式错位 | 选择器基于 dashboard 1.10.8 核对，大版本升级需跟进维护 |

## 开发

```bash
bash /c/Users/38160/Desktop/tools/maibot-devkit/gate.sh /c/Users/38160/Desktop/endfield-theme
```

测试要点：注入→幂等→热更新→停用移除→卸载还原闭环；关键断言对照官方 HTML 原文，
改回旧实现（不压 !important、不清理字体）会让用例失败。

## 许可

- 插件代码：MIT。
- Saira 字体：SIL Open Font License 1.1（`fonts/Saira-OFL.txt`）。
- 设计规则借鉴 endfield-ui-skill（仅规则与 token 数值，CSS 全部自行重写）。
- 不使用任何游戏官方素材。
