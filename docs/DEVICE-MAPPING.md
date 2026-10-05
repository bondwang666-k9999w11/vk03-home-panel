# 米家接入与设备匹配

面板调用 Home Assistant 的 REST API，米家设备需要先在 HA 中可见并可控制。这里把接入和匹配分开说明。

## 1. 先在 HA 接入设备

在 HA“设置 → 设备与服务”中使用支持你的设备型号的集成。可先查阅 [官方 Xiaomi Miio 集成](https://www.home-assistant.io/integrations/xiaomi_miio/)；它支持的型号及接入要求以官方页面为准，并非所有米家设备都由该集成支持。若使用第三方 Xiaomi Home/其他集成，应按该集成自己的文档安装和授权。

先在 HA 网页里验证灯开关、空调模式和净化器开关确实可用，再进行面板匹配。不把集成授权账号或米家密码写入本项目。

## 2. 创建 HA Token

在 HA 用户资料的安全设置中创建长期访问 Token，复制完整内容。只输入本机设备匹配向导，不在 GitHub、截图或聊天中公开。面板访问方式参见 [官方 REST API 文档](https://developers.home-assistant.io/docs/api/rest/)。

## 3. 向导连接与选择

在控制中心点击“HA 设备匹配”，输入例如 `http://homeassistant.local:8123` 的基础地址和 Token，点击“连接并读取设备”。已有 Token 时留空可以复用本机加密凭据。

列表显示友好名称和实体 ID。可以在列表里搜索名称/实体 ID，也可直接填写完整实体 ID。选择后可以修改六个控制卡片的显示名称，超过卡片宽度会显示省略号。

| 面板项目 | 接受的实体类型 | 内容 |
| --- | --- | --- |
| 灯具 1–4 | `switch.*` 或 `light.*` | 使用对应域的 `toggle` |
| 空调 | `climate.*` | 模式、单目标温度、风档、扫风 |
| 净化器 | `fan.*` | 开关；预设模式；无预设时按能力使用百分比风速 |
| 环境温度 | `sensor.*` | 单位为 °C/°F，面板显示 °C |
| 相对湿度 | `sensor.*` | 单位为 %，范围 0–100 |
| PM2.5 / PM10 | `sensor.*` | 显示实体提供的数值和单位 |

同一控制实体不能重复分配给不同按钮。没有设备或不想显示时留空，该位置停用，不会控制其他设备。环境传感器可以来自独立温湿度计，不必来自净化器。

点击“保存并应用设备匹配”后程序保存加密凭据和映射，停止旧面板并重新启动。向导的读取操作不发送任何设备控制命令。

## 4. 不同型号的能力

空调读取 `hvac_modes`、`fan_modes`、`swing_modes`、温度范围/步长及 `supported_features`，不固定使用某台米家设备的中文档位。单位是华氏时，显示转换为摄氏，控制仍发送 HA 原生单位。

净化器读取 `preset_modes`、`percentage` 等属性。预设只显示前 6 个；设备未提供相应能力时不显示操作。风速降到 0% 可能由集成解释为关闭风扇，应以你的设备回报为准。

部分集成暴露的净化器不是 `fan`，或没有标准能力属性，不能直接绑定。可在 HA 中建立符合标准的模板实体，或提出新适配请求；不要仅将实体 ID 前缀改成 `fan`。标准能力见 [Fan entity](https://developers.home-assistant.io/docs/core/entity/fan/) 与 [Climate entity](https://developers.home-assistant.io/docs/core/entity/climate/)。
