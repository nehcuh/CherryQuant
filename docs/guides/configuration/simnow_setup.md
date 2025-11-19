# Simnow 数据源配置指南

## 概述

Simnow是期货模拟交易的官方数据源，提供专业的期货实时行情和历史数据。CherryQuant支持使用Simnow作为主要数据源，提供更专业和稳定的期货数据服务。

## Simnow 账号注册

### 1. 注册流程

1. **访问官网**: [https://www.simnow.com.cn/](https://www.simnow.com.cn/)
2. **点击注册**: 选择"模拟用户注册"
3. **填写信息**:
   - 手机号
   - 邮箱
   - 身份证信息（实名认证）
4. **验证账号**: 通过短信或邮件验证
5. **完成注册**: 获得模拟交易账号

### 2. 账号信息

注册成功后，您会获得以下信息：
- **用户ID**: 通常为手机号或自定义账号
- **密码**: 注册时设置的密码
- **期货公司**: 默认为"Simnow" (代码: 9999)

## CherryQuant 配置

### 1. 环境变量配置

在 `.env` 文件中添加Simnow配置：

```env
# 数据源配置
DATA_SOURCE=simnow

# Simnow账号信息
SIMNOW_USERID=your_simnow_userid
SIMNOW_PASSWORD=your_simnow_password
SIMNOW_BROKER_ID=9999
```

### 2. 配置说明

| 参数 | 说明 | 示例 |
|------|------|------|
| `DATA_SOURCE` | 数据源选择，设置为"simnow" | simnow |
| `SIMNOW_USERID` | Simnow用户ID（手机号） | 13800138000 |
| `SIMNOW_PASSWORD` | Simnow登录密码 | your_password |
| `SIMNOW_BROKER_ID` | 期货公司代码，Simnow固定为9999 | 9999 |

### 3. 配置示例

```env
# OpenAI API配置
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx
OPENAI_BASE_URL=https://api.openai.com/v1

# 期货配置
DEFAULT_SYMBOL=rb2501
EXCHANGE=SHFE

# 数据源配置 - 使用Simnow
DATA_SOURCE=simnow
SIMNOW_USERID=13800138000
SIMNOW_PASSWORD=yourpassword
SIMNOW_BROKER_ID=9999

# 决策配置
DECISION_INTERVAL=300
MAX_POSITION_SIZE=10
LEVERAGE=5
```

## Simnow 服务器信息

### 交易服务器

- **交易服务器地址**: 180.168.146.187
- **交易端口**: 10101
- **备用地址**: 180.168.146.188
- **备用端口**: 10101

### 行情服务器

- **行情服务器地址**: 180.168.146.187
- **行情端口**: 10131
- **备用地址**: 180.168.146.188
- **备用端口**: 10131

## 交易时间

### 日盘
- **集合竞价**: 08:55-08:59
- **日盘交易**: 09:00-15:00

### 夜盘
- **部分品种**: 21:00-次日02:30
- **具体时间**: 根据不同品种而定

### 支持的期货品种

| 交易所 | 品种代码 | 品种名称 |
|--------|----------|----------|
| SHFE | rb | 螺纹钢 |
| SHFE | cu | 沪铜 |
| SHFE | al | 沪铝 |
| SHFE | zn | 沪锌 |
| SHFE | au | 沪金 |
| SHFE | ag | 沪银 |
| DCE | i | 铁矿石 |
| DCE | j | 焦炭 |
| DCE | jm | 焦煤 |
| DCE | m | 豆粕 |
| DCE | y | 豆油 |
| DCE | p | 棕榈油 |
| CZCE | a | 苹果 |
| CZCE | sr | 白糖 |
| CZCE | cf | 棉花 |
| CFFEX | IF | 沪深300股指期货 |
| CFFEX | IC | 中证500股指期货 |
| CFFEX | IH | 上证50股指期货 |

## 数据对比

### AKShare vs Simnow

| 特性 | AKShare | Simnow |
|------|---------|--------|
| **账号要求** | 无需账号 | 需要注册账号 |
| **数据延迟** | 3-5秒 | 实时 |
| **数据质量** | 一般 | 专业级 |
| **稳定性** | 一般 | 高 |
| **历史数据** | 有限 | 完整 |
| **适用场景** | 学习测试 | 专业交易 |

### 推荐配置

#### 学习测试阶段
```env
DATA_SOURCE=akshare
```

#### 实盘准备阶段
```env
DATA_SOURCE=simnow
SIMNOW_USERID=your_userid
SIMNOW_PASSWORD=your_password
```

## 故障排除

### 1. 连接失败

**问题**: Simnow连接失败
**解决方案**:
1. 检查用户ID和密码是否正确
2. 确认Simnow服务器是否正常
3. 检查网络连接
4. 尝试切换到备用服务器

### 2. 数据延迟

**问题**: 行情数据延迟较大
**解决方案**:
1. 检查网络延迟
2. 切换到备用服务器
3. 联系Simnow客服

### 3. 登录失败

**问题**: 账号登录失败
**解决方案**:
1. 确认账号密码正确
2. 检查账号是否被锁定
3. 尝试重置密码
4. 联系Simnow客服

### 4. 品种不支持

**问题**: 某些期货品种无法获取数据
**解决方案**:
1. 确认品种代码是否正确
2. 检查该品种是否在Simnow支持列表中
3. 确认当前时间是否在交易时间内

## 最佳实践

### 1. 账号安全
- 定期修改密码
- 不要分享账号信息
- 使用强密码

### 2. 连接管理
- 设置连接超时时间
- 实现自动重连机制
- 监控连接状态

### 3. 数据管理
- 定期清理历史数据缓存
- 实现数据备份机制
- 监控数据质量

### 4. 性能优化
- 合理设置数据获取频率
- 使用数据压缩传输
- 实现本地数据缓存

## 开发计划

CherryQuant对Simnow的支持正在持续完善中：

### 当前状态 (v0.1.0)
- ✅ 基础框架支持
- ✅ 配置文件支持
- ⏳ CTP网关集成（开发中）
- ⏳ 实时数据推送（开发中）

### 未来计划 (v0.2.0)
- [ ] 完整CTP网关集成
- [ ] 实时行情推送
- [ ] 历史数据批量下载
- [ ] 连接状态监控
- [ ] 自动重连机制

---

**文档版本**: v1.0
**创建日期**: 2025-10-29
**最后更新**: 2025-10-29

更多信息请参考：
- [Simnow官网](https://www.simnow.com.cn/)
- [CherryQuant项目文档](../README.md)
- [数据源架构文档](../design/architecture.md)