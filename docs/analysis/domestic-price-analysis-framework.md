# 国内+国际+市场化+环境资产分析框架（自动化版）

> 为自动化生成周报全场景分析提供的结构化规范
> 基于"周例会营销发言材料"周报的实际分析逻辑整理
> 版本：v1.2
> 适用对象：周报自动化系统开发者、分析师

---

## 0. 文档说明

### 0.1 目的
- 规范周报**全场景**分析的**数据模型、计算逻辑、分析层次**
- 为周报自动化生成提供**可执行的技术规范**
- 确保多周数据**口径一致、可勾稽、可审计**
- 国内段在第 1-14 节、国际段在第 15 节、市场化交易在第 16 节、环境资产在第 17 节

### 0.2 范围
本文档覆盖：
- 集团国内发电收入、上网电量、上网电价的分析（第 1-14 节）
- 集团国际发电收入、上网电量、上网电价的分析（第 15 节，含汇率折算）
- **市场化交易**分析（第 16 节，水电/新能源/火电 3 大板块）
- **环境资产**分析（第 17 节，绿证/CCER 第四类业务）
- 同比、环比双线分析（贯穿各节）

### 0.3 核心输入
**国内段（第 1-14 节）**：
- 上周、上上周、去年同周的电量和电价数据
- 各类电源的发电能力数据
- 水库来水、机组状态等运营数据
- 现货市场、中长期合同价格数据

**国际段（第 15 节）**：
- 各国家原始币种（雷亚尔/欧元/美元/...）的度电与电量
- 各国汇率（CNY/原币种）的当期 + 同比 + 环比值
- 卡洛特等容量电价合同的当期调整
- 各国家、各品类的同比/环比/量价变动明细

**市场化交易段（第 16 节）**：
- 三大板块（水/新/火）的均价 + 同比 + 环比
- 现货市场关键价格（南方、湖北等）
- 现货增收、欠发套利、持仓比例等专项数据
- 火电在运机组状态、系统负荷、各类电源出力变化

**环境资产段（第 17 节）**：
- 绿证核发、销售、库存（按年份 2024/2025/2026 拆分）
- CCER 销售、累计、库存
- 历年绿证价格（用于稀缺性溢价分析）

---

## 1. 数据模型

### 1.1 核心数据字段

```json
{
  "report_id": "2026_W22_001",
  "report_period": {
    "year": 2026,
    "week": 22,
    "start_date": "2026-05-25",
    "end_date": "2026-05-31"
  },
  "group_total": {
    "domestic_ongrid_volume_yi_kwh": 80.3,
    "domestic_avg_price_yuan_per_kwh": 0.311,
    "domestic_revenue_yi_yuan": 24.9,
    "yoy_volume_pct": 3.3,
    "yoy_price_change_fen": -0.9,
    "yoy_revenue_pct": 0.3,
    "mom_volume_pct": 15.7,
    "mom_price_change_fen": 0.1,
    "mom_revenue_pct": 15.9
  },
  "by_category": {
    "hydro": { ... },
    "thermal": { ... },
    "wind": { ... },
    "solar": { ... },
    "renewables_total": { ... }
  },
  "by_region": {
    "hubei": { ... },
    "shandong": { ... },
    "jiangsu": { ... },
    "shaanxi": { ... },
    ...
  }
}
```

### 1.2 单位规范

| 字段 | 单位 | 精度 | 备注 |
|---|---|---|---|
| 上网电量 | 亿千瓦时 | 1 位小数 | 大数据用 |
| 度电价格 | 元/千瓦时 | 3 位小数 | 例 0.311 |
| 价格变化 | 分/千瓦时 | 1 位小数 | 例 −0.9 |
| 收入 | 亿元 | 1 位小数 | 例 24.9 |
| 同比/环比 | % | 1 位小数 | 例 +3.3 |
| 装机 | MW | 整数 | 例 22400 |
| 水位 | 米 | 2 位小数 | 例 145.30 |

### 1.3 必填字段检查清单

- [ ] 集团总量（量、价、收入）
- [ ] 5 大品类（量、价、收入）
- [ ] 同比、环比（量、价、收入）
- [ ] 关键省份至少 4 个（湖北、山东、江苏、陕西）
- [ ] 水库来水数据（如适用）
- [ ] 火电容量电费数据
- [ ] 现货市场、中长期价格数据

---

## 2. 计算公式

### 2.1 基础计算

```python
# 度电均价
avg_price = total_revenue / total_volume

# 收入
revenue = volume * avg_price

# 同比
yoy = (current - last_year) / last_year * 100  # (%)

# 环比
mom = (current - last_week) / last_week * 100  # (%)

# 价格变化（元/度）
price_change_yuan = current_price - last_price

# 价格变化（分/度）
price_change_fen = (current_price - last_price) * 100
```

### 2.2 量价分解（核心公式）

**输入**：
- 各类电源当前电量占比 `share_new`
- 各类电源当前度电 `price_new`
- 各类电源基期电量占比 `share_old`
- 各类电源基期度电 `price_old`
- 集团基期度电 `group_price_old`

**计算**：

```python
# 量化影响（占比变化拉动的均价变化）
quantity_effect = (share_new - share_old) * price_old

# 价格影响（单品类价格变化对均价的拉动力）
price_effect = (price_new - price_old) * share_new

# 合计影响
total_effect = quantity_effect + price_effect

# 验证
assert abs(total_effect - (group_price_new - group_price_old)) < 0.001
```

**单位**：所有结果单位为"元/度"，需要 × 100 转为"分/度"

### 2.3 度电容量电费

```python
# 度电容量电费（元/度）
capacity_fee_per_kwh = total_capacity_fee / total_volume

# 度电容量电费变化
capacity_fee_change = (capacity_fee_new - capacity_fee_old) * 100  # 分/度
```

### 2.4 复合指标计算

```python
# 收入同比分解验证
yoy_revenue = (1 + yoy_volume / 100) * (1 + yoy_price / 100) - 1
# 注意：这是近似，精确计算需用具体数字

# 收入环比分解
mom_revenue = (1 + mom_volume / 100) * (1 + mom_price / 100) - 1
```

### 2.5 勾稽验证公式

```python
# 收入勾稽
assert abs(category_revenue_sum - group_revenue) < 0.1  # 单位亿元

# 收入 = 电量 × 度电
for category in categories:
    expected_revenue = category.volume * category.price
    assert abs(expected_revenue - category.revenue) < 0.1

# 同比环比关系
yoy_growth = (current_revenue - last_year_revenue) / last_year_revenue * 100
mom_growth = (current_revenue - last_week_revenue) / last_week_revenue * 100
```

---

## 3. 分析层次结构

### 3.1 三层金字塔

```
        ┌─────────────────┐
        │   摘要层         │  ← 1 段：总览、关键数字、一句话归因
        │   (What)         │
        └─────────────────┘
                ↓
        ┌─────────────────┐
        │   详细层         │  ← 2-3 段：分品类、分地区、量价分解
        │   (How Much)    │
        └─────────────────┘
                ↓
        ┌─────────────────┐
        │   原因层         │  ← 4-8 段：来水、策略、市场、政策
        │   (Why)          │
        └─────────────────┘
```

### 3.2 各层内容规范

#### 摘要层（必须）
- **总度数、总收入、集团度电均价**
- **同比、环比的双重表达**
- **一句话归因**（哪些品类贡献）

#### 详细层（必须）
- **5 大品类的量、价、收入**
- **量价分解的合计值**
- **关键省份的异常表现**

#### 原因层（按需）
- **每个品类的变化原因**
- **关键省份的策略分析**
- **市场环境（现货、中长期）解读**

---

## 4. 品类分析模板

### 4.1 水电

#### 数据采集
```yaml
hydro:
  volume_yi_kwh: 59.0
  avg_price: 0.283
  revenue_yi: 16.7
  yoy:
    volume_pct: 6.6
    price_change_fen: -0.1
    revenue_pct: 6.2
  mom:
    volume_pct: 19.2
    price_change_fen: -0.4
    revenue_pct: 17.4
  structure:
    jin_xia_pct: 30  # 金下梯级占大水电比例
    qing_jiang_pct: 18  # 清江梯级占水电比例
    san_xia_pct: 40  # 三峡占大水电比例
    pumped_storage_pct: 5  # 抽蓄占水电比例
```

#### 分析触发条件
- 同比电量变化 > ±10%
- 同比度电变化 > ±1 分
- 收入同比变化 > ±20%

#### 输出模板
```
水电度电 [涨/跌] [X] 分，主要原因是：
- 电价较高的 [金下梯级/清江梯级/抽蓄] 电量 [占比提高/下降] [X] 个百分点
- [来水/政策/市场] 影响
对集团度电均价影响 [±X] 分。
```

### 4.2 火电

#### 数据采集
```yaml
thermal:
  volume_yi_kwh: 3.1
  avg_price: 0.421
  revenue_yi: 1.3
  yoy:
    volume_pct: -37.6
    price_change_fen: -3.6
    revenue_pct: -42.5
  mom:
    volume_pct: -10.1
    price_change_fen: 3.4
    revenue_pct: -2.1
  structure:
    capacity_fee: 0.05  # 度电容量电费
    long_term_position_pct: 80  # 中长期持仓
    spot_position_pct: 20  # 现货仓位
    units_operating: 4  # 在运机组数
  market:
    long_term_price: 0.39  # 中长期价格
    spot_price: 0.171  # 现货价格
    capacity_payment_increase: true  # 容量电费是否提高
```

#### 分析触发条件
- 同比电量变化 > ±20%（**火电战略性退场信号**）
- 同比度电变化 > ±5 分
- 中长期合同价格变化 > ±5 分
- 现货价格变化 > ±10%

#### 输出模板
```
火电度电 [涨/跌] [X] 分，主要原因是：
- 中长期合同价格 [涨/跌] [X] 分/度
- 现货市场均价 [涨/跌] [X]%
- [容量电费提高/降低] 度电容量电费 [X] 分
- [欠发套利/多发] 策略
- 集团 [X] 台机组在运
```

### 4.3 风电

#### 数据采集
```yaml
wind:
  volume_yi_kwh: 10.4
  avg_price: 0.412
  revenue_yi: 4.3
  yoy:
    volume_pct: 11.8
    price_change_fen: -0.7
    revenue_pct: 9.9
  mom:
    volume_pct: 28.4
    price_change_fen: 1.7
    revenue_pct: 34.0
  structure:
    offshore_pct: 26  # 海风占比
    onshore_pct: 74
  resources:
    offshore_resource: "high"  # 高/中/低
    onshore_resource: "high"
```

#### 分析触发条件
- 海风占比变化 > ±3 pp
- 同比度电变化 > ±1 分
- 海风资源异常（高/低）

#### 输出模板
```
风电度电 [涨/跌] [X] 分，主要原因是：
- 海风占比 [提高/降低] [X] 个百分点，拉高均价 [X] 分
- [江苏/山东/广东] 等地风电电价 [涨/跌]
- 海风/陆风资源 [好/差]
```

### 4.4 光伏

#### 数据采集
```yaml
solar:
  volume_yi_kwh: 7.6
  avg_price: 0.340
  revenue_yi: 2.6
  yoy:
    volume_pct: -3.8
    price_change_fen: -2.6
    revenue_pct: -10.5
  mom:
    volume_pct: -6.6
    price_change_fen: 1.1
    revenue_pct: -3.1
  resources:
    solar_resource: "low"  # 资源条件
  by_region:
    hubei:
      yoy_price_change: 0
      mom_price_change: 3.0
      strategy: "95% long-term"
    shandong:
      mom_price_change: 5.8
      strategy: "0% long-term"
```

#### 分析触发条件
- 度电变化 > ±2 分
- 资源条件异常
- 关键省份策略变化

#### 输出模板
```
光伏度电 [涨/跌] [X] 分，主要原因是：
- [省份] 电价 [涨/跌]（[原因]）
- 低价地区/高价地区 电量占比 [变化]
- 光伏资源 [好/差]
```

### 4.5 新能源（合并）

```yaml
renewables_total:
  # = 风电 + 光伏 + 其他
  volume_yi_kwh: 18.0
  avg_price: 0.381
  revenue_yi: 6.8
```

**分析原则**：当周报以"新能源"为单位披露时，**风电和光伏的合计**；当以"风电""光伏"分开披露时，**分别分析**。

---

## 5. 地区分析模板

### 5.1 关键省份清单

| 省份 | 重要性 | 关键电源 | 典型策略 |
|---|---|---|---|
| **湖北** | ⭐⭐⭐⭐⭐ | 水电 + 火电 | 95% 锁价 / 现货博弈 |
| **山东** | ⭐⭐⭐⭐⭐ | 火电 + 风电 + 光伏 | 0% 持仓 / 现货套利 |
| **江苏** | ⭐⭐⭐⭐⭐ | 海风 + 火电 | 补贴海风结构 |
| **陕西** | ⭐⭐⭐⭐ | 光伏 + 风电 | 105% 监管红线 |
| **内蒙** | ⭐⭐⭐ | 陆风 + 火电 | 低价区 |
| **青海** | ⭐⭐⭐ | 光伏 + 水电 | 低价区 |
| **山西** | ⭐⭐⭐ | 火电 + 风电 | 低价区 |
| **吉林** | ⭐⭐ | 风电 + 光伏 | 高价区 |
| **浙江** | ⭐⭐ | 风电 + 光伏 | 高价区 |

### 5.2 省份分析维度

```yaml
province:
  name: "湖北"
  main_sources: ["hydro", "thermal"]
  price_change_fen: 3.0  # 度电变化（分/度）
  market:
    spot_avg_price: 0.171
    long_term_price: 0.35
  strategy:
    long_term_position: 95  # 中长期持仓比例
    spot_position: 5
  key_factors:
    - "阴雨天气"
    - "水电大发"
    - "现货价格走低"
  trigger_reason: "高比例中长期持仓策略"
```

### 5.3 "一省一策"模式库

| 模式 | 特征 | 触发条件 | 风险 |
|---|---|---|---|
| **高持仓锁价** | 80-95% 中长期 | 现货价 < 中长期价 | 现货反弹时少赚 |
| **低持仓博现货** | 0-15% 中长期 | 现货价 > 中长期价 | 现货跌穿时亏损 |
| **105% 卡线** | 持仓 ≤ 105% | 监管限制超持仓 | 错过超额套利 |
| **0% 全现货** | 全部走现货 | 短期供需紧张 | 价格大幅波动 |

---

## 6. 异常检测规则

### 6.1 度电异常

| 指标 | 阈值 | 触发动作 |
|---|---|---|
| 度电同比变化 > ±5 分 | 触发 | 详细分析原因 |
| 度电环比变化 > ±3 分 | 触发 | 详细分析原因 |
| 度电同比变化 > ±10 分 | **重点** | 高级别异常告警 |

### 6.2 电量异常

| 指标 | 阈值 | 触发动作 |
|---|---|---|
| 电量同比变化 > ±10% | 触发 | 分析来水/装机变化 |
| 电量环比变化 > ±20% | 触发 | 分析天气/检修 |
| 火电同比 < −30% | **重点** | 战略性退场预警 |

### 6.3 收入异常

| 指标 | 阈值 | 触发动作 |
|---|---|---|
| 收入同比变化 > ±20% | 触发 | 量价分解 |
| 火电收入同比 < −30% | **重点** | 战略调整说明 |
| 集团收入同比 < 0% | 触发 | 业绩预警 |

### 6.4 占比异常

| 指标 | 阈值 | 触发动作 |
|---|---|---|
| 单一品类占比变化 > ±5 pp | 触发 | 结构变化分析 |
| 火电占比 < 5% | **提示** | 战略性边缘化 |
| 新能源占比 > 30% | **提示** | 转型里程碑 |

### 6.5 水库异常

| 指标 | 阈值 | 触发动作 |
|---|---|---|
| 来水同比偏丰/偏枯 > ±50% | 触发 | 重点分析 |
| 累计完成率 < 时间进度 −10 pp | **重点** | 蓄水策略评估 |
| 周完成率 < 90% | 触发 | 调度问题排查 |

---

## 7. 语言模式库

### 7.1 业绩归因话术

#### 业绩上涨
```
上周，集团公司国内发电收入 [X] 亿元，[同比/环比] 提高 [X]%，
主要原因是 [品类 A、B] 收入 [同比/环比] 提高。
```

#### 业绩下跌
```
上周，集团公司国内发电收入 [X] 亿元，[同比/环比] 下降 [X]%，
主要原因是 [品类 A] 收入下降，抵消了 [品类 B] 收入提高的影响。
```

#### 量价分别变化
```
上网电量 [同比/环比] 提高 [X]%，主要原因是 [来水/装机/政策] ；
度电均价 [涨/跌] [X] 分，主要原因是 [结构/价格/容量电费] 。
```

### 7.2 量价博弈话术

#### 以量补价
```
电量同比提高 [X]%，度电下降 [X] 分，收入 [持平/微增]，
"以量补价" 策略 [有效/接近极限] 。
```

#### 量价齐升
```
量价齐升：电量 [同比/环比] [X]%，度电 [涨/跌] [X] 分，
收入 [大幅] 提高 [X]%。
```

#### 量价齐跌
```
量价齐跌：电量 [同比/环比] [X]%，度电 [涨/跌] [X] 分，
收入 [大幅] 下降 [X]%。
```

### 7.3 业务结构话术

#### 结构优化
```
[品类 A] 占比提高 [X] 个百分点，[品类 B] 占比下降 [X] 个百分点，
集团电源结构 [进一步优化/转型] 。
```

#### 战略性退场
```
[品类] 电量同比下降 [X]%，收入下降 [X]%，
符合 [双碳/转型] 战略方向。
```

### 7.4 风险预警话术

#### 长期挑战
```
虽然 [环比/短期] 数据好转，但 [同比/长期] 仍 [跌/承压]，
反映 [市场化/补贴退坡] 的 [长期/持续] 影响。
```

#### 风险提示
```
需要关注 [现货价格波动/补贴退坡/政策变化/来水形势] 的影响。
```

### 7.5 调度策略话术

#### 蓄水策略
```
[水库] 累计完成率 [X]%，[低于/高于] 时间进度 [X] pp，
符合 [汛前蓄水/保供] 调度策略。
```

#### 欠发套利
```
[省份] 火电通过 [调减/增加] 中长期仓位（[X]% → [Y]%），
[欠发/多发] 套利，[提高/降低] 整体价格。
```

---

## 8. 输出格式模板

### 8.1 摘要段模板

```markdown
上周（[开始日期] ~ [结束日期]），集团公司国内
发电收入 [X] 亿元，[同比/环比] 提高 [X]%
（上网电量 [同比/环比] 提高 [X]%），主要原因是
[品类 A]、[品类 B] 收入 [同比/环比] 提高。
度电均价 [X] 元/度，[同比/环比] [涨/跌] [X] 分。
```

### 8.2 详细段模板（按品类）

```markdown
各品类中：
- 水电：电量 [X] 亿度（[同比/环比] [X]%），
  度电 [X] 元（[同比/环比] [X] 分），
  收入 [X] 亿元（[同比/环比] [X]%）
- 火电：[同上结构]
- 风电：[同上结构]
- 光伏：[同上结构]
```

### 8.3 量价分解段模板

```markdown
电量结构变化影响度电均价 [X] 分、电价变化影响度电均价 [X] 分。
各品类中：
- 水电：占比 [提高/降低] [X] pp，度电 [涨/跌] [X] 分，
  量价合计影响 [X] 分
- 火电：[同上]
- 风电：[同上]
- 光伏：[同上]
```

### 8.4 原因段模板

```markdown
其中，[品类] 度电 [涨/跌] 的原因是：
1. [内部结构因素]
2. [政策/市场因素]
3. [资源/策略因素]
```

---

## 9. 异常告警级别

| 级别 | 触发条件 | 响应 |
|---|---|---|
| **🔴 严重** | 收入同比 < −30% / 集团完成率 < 60% | 立即告警 + 详细分析 |
| **🟠 重要** | 收入变化 > ±20% / 度电变化 > ±5 分 | 详细分析 |
| **🟡 一般** | 收入变化 > ±10% / 度电变化 > ±2 分 | 简要说明 |
| **🟢 正常** | 收入变化 ≤ ±10% / 度电变化 ≤ ±2 分 | 标准报告 |

---

## 10. 自动化数据流

### 10.1 整体流程

```
数据采集
  ↓
数据清洗（单位、口径校验）
  ↓
基础计算（量、价、收入）
  ↓
同比/环比计算
  ↓
量价分解
  ↓
异常检测
  ↓
品类分析（按模板生成）
  ↓
地区分析（按模板生成）
  ↓
原因分析（按规则生成）
  ↓
文本生成（自然语言输出）
  ↓
勾稽验证
  ↓
报告输出
```

### 10.2 数据采集

```yaml
data_sources:
  - source: 集团周报 Excel
    frequency: 每周
    format: xlsx
    fields: [volume, price, revenue, ...]
  
  - source: 各省现货市场数据
    frequency: 每日
    format: API/CSV
    fields: [spot_price, long_term_price, ...]
  
  - source: 关键电站运行数据
    frequency: 实时
    format: API
    fields: [output, water_level, ...]
```

### 10.3 计算引擎核心函数

```python
def analyze_weekly_price(data: WeeklyData) -> WeeklyReport:
    # 1. 基础计算
    group_metrics = calculate_group_metrics(data)
    
    # 2. 同比环比
    yoy_metrics = calculate_yoy(group_metrics, last_year_data)
    mom_metrics = calculate_mom(group_metrics, last_week_data)
    
    # 3. 量价分解
    decomposition = decompose_volume_price(data)
    
    # 4. 异常检测
    anomalies = detect_anomalies(group_metrics, yoy_metrics, mom_metrics)
    
    # 5. 品类分析
    category_analysis = analyze_categories(data)
    
    # 6. 地区分析
    region_analysis = analyze_regions(data)
    
    # 7. 文本生成
    summary = generate_summary(group_metrics, yoy_metrics, mom_metrics)
    details = generate_details(category_analysis)
    reasons = generate_reasons(category_analysis, region_analysis)
    
    # 8. 勾稽验证
    validate(report)
    
    return WeeklyReport(summary, details, reasons)
```

### 10.4 模板引擎示例

```python
TEMPLATES = {
    'summary_up': """
上周（{start_date} ~ {end_date}），集团公司国内
发电收入 {revenue} 亿元，同比提高 {yoy_pct}%
（上网电量同比提高 {yoy_vol_pct}%），主要原因是
{top_categories_text} 收入同比提高。
""",
    
    'summary_down': """
上周（{start_date} ~ {end_date}），集团公司国内
发电收入 {revenue} 亿元，同比下降 {yoy_pct}%
（上网电量同比下降 {yoy_vol_pct}%），主要原因是
{top_categories_text} 收入下降。
""",
    
    'reason_hydro_volume_up': """
水电同比/环比提高 {pct}%，主要原因是
{reason_1}，{reason_2}。
""",
}
```

---

## 11. 关键提示词库

### 11.1 数据缺失处理

| 场景 | 处理方式 |
|---|---|
| 省份数据缺失 | 用集团平均填充 + 标记"待补充" |
| 现货价格缺失 | 用近期均价填充 + 标记"估算" |
| 同比基期数据缺失 | 跳过同比分析，只做环比 |
| 数据异常 | 触发人工审核流程 |

### 11.2 文本生成约束

- 同类语言避免重复（用同义词）
- 保持术语一致
- 数字精度统一
- 单位一致
- 控制文本长度

### 11.3 校验规则

- 数字勾稽 100% 通过
- 同比/环比方向正确
- 量价分解合计 = 集团均价变化
- 收入 = 电量 × 度电

---

## 12. 业务规则库

### 12.1 火电战略性退场检测

```python
def is_thermal_retreat(data):
    return (
        data['yoy_volume_pct'] < -30 and  # 同比电量 < -30%
        data['group_share'] < 0.05  # 占比 < 5%
    )
```

### 12.2 度电价格水平判断

```python
def price_level(price):
    if price < 0.30:
        return "偏低（水电主导）"
    elif price < 0.40:
        return "中等"
    else:
        return "偏高（火电/海风主导）"
```

### 12.3 业务结构判断

```python
def business_structure(data):
    hydro_share = data['hydro_volume'] / data['total_volume']
    renewable_share = (data['wind_volume'] + data['solar_volume']) / data['total_volume']
    thermal_share = data['thermal_volume'] / data['total_volume']
    
    if hydro_share > 0.7:
        return "水电主导型"
    elif renewable_share > 0.4:
        return "新能源主导型"
    elif thermal_share > 0.5:
        return "火电主导型"
    else:
        return "混合型"
```

---

## 13. 实施优先级

### Phase 1（基础）
- [x] 5 大品类量、价、收入基础数据
- [x] 同比、环比计算
- [x] 集团汇总
- [x] 基础异常检测

### Phase 2（详细）
- [ ] 量价分解
- [ ] 关键省份分析
- [ ] 语言模板生成
- [ ] 数字勾稽验证

### Phase 3（高级）
- [ ] 多周趋势分析
- [ ] 战略预警
- [ ] 自动归因
- [ ] 异常告警分级

### Phase 4（智能化）
- [ ] 机器学习预测
- [ ] 异常根因分析
- [ ] 自然语言生成优化
- [ ] 行业对标

---

## 14. 附录

### 14.1 名词对照表

| 全称 | 简称 |
|---|---|
| 上网电量 | 量 |
| 上网电价 | 价 |
| 度电均价 | 度电 |
| 度电价格变化 | 度电变化 |
| 中长期合同 | 中长期 |
| 现货市场 | 现货 |
| 抽水蓄能 | 抽蓄 |
| 海风/陆风 | 海上风电/陆上风电 |
| 平价装机 | 无补贴项目 |

### 14.2 单位换算

```
1 亿千瓦时 = 10^8 千瓦时 = 10^8 度
1 度 = 1 千瓦时
1 元 = 100 分 = 1000 厘

1 亿度 × 1 分/度 = 100 万元
80 亿度 × 0.9 分/度 = 7,200 万元
```

### 14.3 关键数字参考

| 指标 | 典型值 |
|---|---|
| 集团周上网电量 | 80-100 亿度 |
| 集团周发电收入 | 20-30 亿元 |
| 集团度电均价 | 0.30-0.40 元 |
| 水电占比 | 60-80% |
| 火电占比 | 5-30% |
| 新能源占比 | 15-30% |

---

## 15. 国际电价分析框架

> 本节定义国际上网电价分析的**数据模型、归因方法、区域模板、自动化流程**。
> 国内段在第 1-14 节，国际段特有问题（汇率折算、多币种、区域分化、合同结构）在本节集中处理。

### 15.1 数据模型

#### 15.1.1 顶层数据字段

```json
{
  "report_id": "2026_W21_001",
  "international": {
    "total_volume_yi_kwh": 8.8,
    "total_revenue_yi_yuan": 28.2,
    "avg_price_yuan_per_kwh": 0.32,
    "yoy_price_change_fen": 3.9,
    "mom_price_change_fen": 1.3,
    "yoy_volume_pct": 0,
    "mom_volume_pct": 0,
    "yoy_revenue_pct": 0,
    "mom_revenue_pct": 0
  },
  "attribution_three_layer": {
    "exchange_rate_effect_fen": 1.0,
    "contract_effect_fen": 0.2,
    "real_business_effect_fen": 2.7
  },
  "by_region": {
    "latin_america": { "...": "巴西、秘鲁等" },
    "europe": { "...": "西班牙等" },
    "asia_africa": { "...": "巴基斯坦、缅甸等" },
    "north_america": { "...": "美国、加拿大" },
    "other": { "...": "其他" }
  },
  "by_category": {
    "hydro": { "...": "水电" },
    "wind": { "...": "风电" },
    "solar": { "...": "光伏" }
  },
  "by_company": {
    "three_gorges_intl": { "...": "三峡国际" },
    "cyg_intl": { "...": "长电国际" },
    "hubei_energy": { "...": "湖北能源" }
  },
  "exchange_rates": {
    "CNY_BRL": { "current": 1.30, "yoy_pct": 7.6, "mom_pct": -0.5 },
    "CNY_USD": { "current": 7.20, "yoy_pct": -5.6, "mom_pct": -0.1 },
    "CNY_EUR": { "current": 7.80, "yoy_pct": -30.0, "mom_pct": -0.5 }
  },
  "contracts": {
    "karot_capacity": { "current_fen": 0.2, "yoy_fen": 0.2, "mom_fen": -0.02 }
  }
}
```

#### 15.1.2 按国家 × 品类二维细分

```json
{
  "by_country_category": [
    {
      "country": "巴西",
      "currency": "BRL",
      "category": "hydro",
      "volume_yi_kwh": 3.5,
      "avg_price_local": 0.27,
      "avg_price_cny": 0.351,
      "yoy_price_change_fen": 1.6,
      "mom_price_change_fen": -0.1,
      "yoy_volume_change_pct": -5.0,
      "mom_volume_change_pct": -2.0,
      "yoy_yuan_effect_fen": 1.6,
      "mom_yuan_effect_fen": -0.1
    },
    {
      "country": "西班牙",
      "currency": "EUR",
      "category": "wind",
      "volume_yi_kwh": 1.2,
      "avg_price_local": 0.08,
      "avg_price_cny": 0.624,
      "yoy_price_change_fen": 0.4,
      "mom_price_change_fen": 1.2,
      "yoy_volume_change_pct": 8.0,
      "mom_volume_change_pct": 12.0,
      "yoy_yuan_effect_fen": 0.4,
      "mom_yuan_effect_fen": 1.2
    }
  ]
}
```

#### 15.1.3 必填字段检查清单（国际段）

- [ ] 国际总量（量、价、收入）
- [ ] 三层归因（汇率/合同/真本事）合计与总变化勾稽
- [ ] 5 区域至少 3 个有数据（拉美/欧洲/亚非）
- [ ] 3 大品类（水/风/光）分国家数据
- [ ] 至少 3 种货币的当期 + 同比 + 环比汇率
- [ ] 容量电价合同（卡洛特等）的当期调整
- [ ] 3 个国际运营主体（三峡国际/长电国际/湖北能源）的度电变化
- [ ] 排除汇率/合同影响后的"内生"分项数据

#### 15.1.4 单位规范（国际段特有）

| 字段 | 单位 | 备注 |
|---|---|---|
| 国际度电（人民币口径）| 元/千瓦时 | 已折算 |
| 国际度电（当地口径）| 当地币种/千瓦时 | **必须**双口径 |
| 价格变化 | 分/千瓦时 | 统一用人民币口径 |
| 汇率 | CNY/原币种 | 6 位小数 |
| 汇率变化 | % | 1 位小数 |
| 国际收入 | 亿元（人民币）| 已折算 |
| 各国家电量 | 亿千瓦时 | 1 位小数 |

---

### 15.2 计算公式

#### 15.2.1 基础计算（含汇率折算）

```python
# 各国家度电（人民币口径）
def local_to_cny_price(local_price, exchange_rate):
    """当地币种 → 人民币"""
    return local_price * exchange_rate

# 集团国际度电（人民币口径，加权平均）
group_international_price_cny = sum(
    country.avg_price_cny * country.volume_yi_kwh
    for country in countries
) / sum(country.volume_yi_kwh for country in countries)

# 国际收入
international_revenue = group_international_price_cny * total_volume_yi_kwh * 1e8
```

#### 15.2.2 三层归因分解（核心公式）

**核心思想**：把"度电变化"拆为"汇率 + 合同 + 真本事"三层。

```python
def three_layer_attribution(
    current_price_cny,
    last_year_price_cny,
    current_exchange_rates,
    last_year_exchange_rates,
    current_contracts,
    last_year_contracts
):
    """
    三层归因：
    - 汇率层：纯汇率变动对度电的拉动力
    - 合同层：卡洛特等合同价格调整
    - 真本事层：剩余的内生增长（结构 + 量价）
    """
    # 第一层：汇率影响
    # 假设当地价不变、汇率变化引起的度电变化
    exchange_effect = compute_exchange_effect(
        last_year_local_prices, current_exchange_rates
    ) - compute_exchange_effect(
        last_year_local_prices, last_year_exchange_rates
    )
    
    # 第二层：合同影响（卡洛特等）
    contract_effect = (
        current_contracts.karot - last_year_contracts.karot
    ) * 100  # 分/度
    
    # 第三层：真本事（剩余项）
    total_change_fen = (current_price_cny - last_year_price_cny) * 100
    real_business_effect = total_change_fen - exchange_effect - contract_effect
    
    return {
        "exchange_rate_effect_fen": exchange_effect,
        "contract_effect_fen": contract_effect,
        "real_business_effect_fen": real_business_effect,
        "total_change_fen": total_change_fen
    }


def compute_exchange_effect(local_prices, exchange_rates):
    """
    计算"假设当地价不变、汇率变为 X"时的集团度电
    """
    weighted_sum = sum(
        local_prices[country] * exchange_rates[country] * country.volume
        for country in countries
    )
    total_volume = sum(country.volume for country in countries)
    return weighted_sum / total_volume
```

**单位**：所有结果单位为"分/度"。

#### 15.2.3 品类层归因（真本事的二级分解）

```python
def category_attribution(yoy_or_mom_data):
    """
    把"真本事 X 分"按品类（水/风/光）拆开
    """
    return {
        "hydro_effect_fen": sum(
            country.effect_fen for country in countries if country.category == "hydro"
        ),
        "wind_effect_fen": sum(
            country.effect_fen for country in countries if country.category == "wind"
        ),
        "solar_effect_fen": sum(
            country.effect_fen for country in countries if country.category == "solar"
        )
    }
```

#### 15.2.4 勾稽验证公式

```python
# 三层归因合计 = 总变化
assert abs(
    exchange_effect + contract_effect + real_business_effect - total_change_fen
) < 0.01  # 单位：分/度

# 品类层归因合计 = 真本事
assert abs(
    hydro_effect + wind_effect + solar_effect - real_business_effect
) < 0.01

# 分公司影响合计 = 总变化
assert abs(
    sum(company.effect_fen for company in companies) - total_change_fen
) < 0.05

# 收入勾稽
assert abs(
    sum(category.revenue for category in categories) - total_revenue
) < 0.1
```

---

### 15.3 归因三层框架（汇率 / 合同 / 真本事）

#### 15.3.1 第一层：汇率层

| 字段 | 说明 |
|---|---|
| **输入** | 各国家原币种度电、各国汇率（当期 + 基期） |
| **输出** | "假设当地价不变、汇率变了"对集团度电的拉动力 |
| **常见误用** | ❌ 用"汇率变化"直接乘以总收入 |
| **正确做法** | ✅ 用基期当地价 × 汇率变化 = 汇率层影响 |

#### 15.3.2 第二层：合同层

| 字段 | 说明 |
|---|---|
| **输入** | 各容量电价合同的当期 vs 基期 |
| **典型案例** | 卡洛特容量电价（巴基斯坦）|
| **输出** | 合同价格调整对度电的拉动力 |
| **判断标准** | 是否属于"一次性"、"外部输入"、"非结构变化"|

#### 15.3.3 第三层：真本事层

| 字段 | 说明 |
|---|---|
| **输入** | 排除汇率 + 合同后剩余的变化 |
| **二级分解** | 品类（水/风/光）× 区域（拉美/欧洲/亚非/...）|
| **价值评估** | ⭐ **这是真正反映"主动经营能力"的部分** |
| **持续性** | ✅ 可持续、可复制、有战略意义 |

#### 15.3.4 三层关系的本质

```
总变化 = 汇率层 + 合同层 + 真本事层
         (不可控)  (一次性)  (可持续 ⭐)
```

**核心判断**：
- 真本事 > 汇率：✅ 主动能力强
- 真本事 > 合同：✅ 经营能力主导
- 汇率占主导：⚠️ 警惕"汇率幻觉"

---

### 15.4 5 区域分析模板

#### 15.4.1 拉美（巴西、秘鲁等）

```yaml
latin_america:
  typical_currency: BRL（巴西雷亚尔）、PEN（秘鲁新索尔）
  typical_sources: hydro（水电为主）
  price_mechanism: PPA + 市场化混合
  key_risks:
    - 汇率波动大（雷亚尔 5 年波动 50%+）
    - 来水不稳定（厄尔尼诺影响）
    - 巴西水电行业均摊政策（滞后结算）
  analysis_triggers:
    - 雷亚尔月度波动 > ±5%
    - 来水同比偏丰/偏枯 > ±20%
  output_template: |
    拉美区域度电 [涨/跌] [X] 分，主要原因是：
    - 巴西水电 [电量变化] + [电价变化]
    - 秘鲁水电 [类似结构]
    - 雷亚尔 [升值/贬值] [X]%
```

#### 15.4.2 欧洲（西班牙、葡萄牙、德国等）

```yaml
europe:
  typical_currency: EUR（欧元）
  typical_sources: wind（风电为主）、solar
  price_mechanism: 市场化电价为主 + 部分 PPA
  key_risks:
    - 欧盟政策（CBAM、补贴退坡）
    - 电力批发市场波动
    - 西班牙新能源补贴（滞后结算）
  analysis_triggers:
    - 欧元月度波动 > ±3%
    - 欧洲电力现货价格 > 100 EUR/MWh
  output_template: |
    欧洲区域度电 [涨/跌] [X] 分，主要原因是：
    - 风电 [电量变化] + [电价变化]
    - 光伏 [类似结构]
    - 欧元 [升值/贬值] [X]%
```

#### 15.4.3 亚非（巴基斯坦、缅甸、尼泊尔等）

```yaml
asia_africa:
  typical_currency: USD（美元结算为主）
  typical_sources: hydro、thermal、wind
  price_mechanism: PPA + 双轨制
  key_risks:
    - 美元汇率波动
    - 电费回收风险
    - 地缘政治
  analysis_triggers:
    - 项目所在国主权评级变化
    - 美元月度波动 > ±2%
  output_template: |
    亚非区域度电 [涨/跌] [X] 分，主要原因是：
    - [品类] [电量变化] + [电价变化]
    - 卡洛特容量电价 [调整] [X] 分
    - 美元 [升值/贬值] [X]%
```

#### 15.4.4 北美（美国、加拿大）

```yaml
north_america:
  typical_currency: USD
  typical_sources: wind、solar
  price_mechanism: PPA（10-20 年长协）
  key_risks:
    - 美元利率
    - 美国 IRA 政策变化
  analysis_triggers:
    - 美元利率变化 > ±50bp
```

#### 15.4.5 其他

```yaml
other:
  typical_sources: 综合
  analysis_triggers: 异常分析
```

---

### 15.5 同比环比双线分析模板

#### 15.5.1 总账对比表

```markdown
| 指标 | 同比 | 环比 | 解读 |
|------|------|------|------|
| 总变化 | +X 分 | +X 分 | 长期/短期方向 |
| 汇率 | ±X | ±X | 方向是否反转 |
| 合同 | ±X | ±X | 一次性事件影响 |
| 真本事 | ±X | ±X | 内生增长能力 |
```

#### 15.5.2 品类结构对比表

```markdown
| 品类 | 同比 | 环比 | 动能判断 |
|------|------|------|---------|
| 水电 | +X | -X | ⚠️ 转负 |
| 风电 | +X | +X | 🚀 加速 |
| 光伏 | ±X | -X | 📉 拖累 |
```

#### 15.5.3 区域分化对比表

```markdown
| 区域 | 同比 | 环比 | 解读 |
|------|------|------|------|
| 拉美 | +X | -X | 巴西/秘鲁分化 |
| 欧洲 | +X | +X | 风电独大 |
| 亚非 | +X | +X | 卡洛特稳定 |
```

#### 15.5.4 三大核心判断

```python
def international_yoy_mom_analysis(yoy_data, mom_data):
    """
    输出三大核心判断
    """
    return {
        "capability_dimension": {
            "yoy_real_business": yoy_data.real_business_effect,
            "verdict": "能力在积累" if yoy_data.real_business_effect > 0 else "能力承压"
        },
        "momentum_dimension": {
            "mom_real_business": mom_data.real_business_effect,
            "yoy_to_mom_change": mom_data.real_business_effect - yoy_data.real_business_effect,
            "verdict": "动能减弱" if mom_data.real_business_effect < yoy_data.real_business_effect else "动能加速"
        },
        "structure_dimension": {
            "yoy_engine_count": count_positive_categories(yoy_data),
            "mom_engine_count": count_positive_categories(mom_data),
            "verdict": "结构集中" if mom_data.engine_count < yoy_data.engine_count else "结构分散"
        }
    }
```

---

### 15.6 异常检测规则（国际段特有）

#### 15.6.1 汇率异常

| 指标 | 阈值 | 触发动作 |
|---|---|---|
| 单一币种月度波动 > ±5% | 触发 | 详细分析汇率层影响 |
| 雷亚尔年度波动 > ±30% | **重点** | 高层关注汇率风险 |
| 多种货币同时大幅波动 | **重点** | 评估对冲必要性 |

#### 15.6.2 区域异常

| 指标 | 阈值 | 触发动作 |
|---|---|---|
| 单一国家占国际收入 > 50% | 触发 | 集中度风险评估 |
| 单一国家度电同比变化 > ±10 分 | 触发 | 项目级归因 |
| 单一国家连续 2 周同比 < −5 分 | **重点** | 战略级预警 |

#### 15.6.3 合同异常

| 指标 | 阈值 | 触发动作 |
|---|---|---|
| 容量电价合同调整 > ±0.5 分 | 触发 | 合同层归因 |
| 单一合同占国际收入 > 30% | **重点** | 合同集中度风险 |

#### 15.6.4 归因异常

| 指标 | 阈值 | 触发动作 |
|---|---|---|
| 汇率层影响 > 真本事层 2 倍 | 警告 | "汇率幻觉"风险 |
| 合同层连续 2 周超过 ±0.3 分 | 触发 | 合同集中到期 |
| 排除汇率/合同后真本事 < 0 | **重点** | 经营能力预警 |

---

### 15.7 语言模式库（国际段）

#### 15.7.1 同比话术

```
国际上网电价约每千瓦时 [X] 元，[同比/环比] 提高 [X] 分，
主要外币汇率变动（[币种 1] [升/贬]值 [X]%、[币种 2] [升/贬]值 [X]%）
影响国际度电均价 [提高/下降] 约 [X] 分、
[合同名称] 容量电价变动影响国际度电均价 [提高/下降] 约 [X] 分，
排除汇率、[合同名称] 容量价格变动影响后，
[同比/环比] 提高度电约 [X] 分，
汇率、[合同名称] 容量价格以外的主要原因是 [原因 1]、[原因 2]。
```

#### 15.7.2 环比话术（同结构）

环比话术结构与同比完全相同，**只需替换"同比"为"环比"**。

#### 15.7.3 品类层归因话术

```
一是各区域 [品类] 量价变动影响国际度电均价 [提高/下降] 约 [X] 分：
- [国家 1] [品类] [电量描述]、[电价描述]，
  影响国际度电均价 [提高/下降] 约 [X] 分；
- [国家 2] [类似结构]。
```

#### 15.7.4 分公司归因话术

```
[分公司名称] 度电均价 [同比/环比] [提高/下降] 约 [X] 分
[排除汇率、[合同名称] 容量价格变动影响后 [同比/环比] [提高/下降] 约 [X] 分]、
影响 [集团/国际] 度电均价 [提高/下降] 约 [X] 分
[排除汇率、[合同名称] 容量价格变动影响后 [提高/下降] 约 [X] 分]。
```

#### 15.7.5 区域分化话术

```
各区域分化明显：
- [区域 1]：[正向描述]，[品类] [量价变化]
- [区域 2]：[负向描述]，[原因]
- [区域 3]：[中性描述]，[原因]
```

---

### 15.8 输出格式模板

#### 15.8.1 国际段总览模板

```markdown
上周（[开始日期] ~ [结束日期]），集团公司国际
上网电价 [X] 元/度，[同比/环比] [提高/下降] [X] 分
（[W报中未考虑 X、Y 两个滞后结算收入项目的影响]）。
```

#### 15.8.2 国际段同比段模板

```markdown
[同比] [提高/下降] [X] 分，主要外币汇率变动
（[币种 1] [升/贬]值 [X]%、[币种 2] [升/贬]值 [X]%、[币种 3] [升/贬]值 [X]%）
影响度电均价 [提高/下降] 约 [X] 分、
[合同名称] 容量电价变动影响度电均价 [提高/下降] 约 [X] 分；
排除汇率、[合同名称] 容量价格变动影响后，
[同比] [提高/下降] 度电约 [X] 分，
汇率、[合同名称] 容量价格以外的主要原因是 [原因 1]、[原因 2]。
```

#### 15.8.3 国际段环比段模板（同比模板基础上改"同比"为"环比"）

#### 15.8.4 国际段品类归因模板

```markdown
一是各区域 [品类] 量价变动影响国际度电均价 [提高/下降] 约 [X] 分：
- [国家 1] [品类] [电量描述]、[电价描述]，
  影响国际度电均价 [提高/下降] 约 [X] 分；
- [国家 2] [品类] [类似描述]。

二是各区域 [品类] 量价变动影响 [度电/国际度电] 均价 [提高/下降] 约 [X] 分：
- [同上结构]。

三是各区域 [品类] 量价变动影响 [度电/国际度电] 均价 [提高/下降] 约 [X] 分：
- [同上结构]。
```

#### 15.8.5 国际段分公司归因模板

```markdown
[分公司 A] 度电均价 [同比/环比] [提高/下降] 约 [X] 分
[[排除汇率、[合同名称] 容量价格变动影响后 [同比/环比] [提高/下降] 约 [X] 分]、
[高价/低价] 电量占比 [提高/下降] [X] 个百分点，
影响国际度电均价 [提高/下降] 约 [X] 分]。
[分公司 B] [类似结构]。
[分公司 C] [类似结构]。）
```

---

### 15.9 自动化数据流（国际段）

#### 15.9.1 整体流程

```
汇率数据采集
   ↓
各国家原始数据采集（量、当地度电）
   ↓
汇率折算（当地价 → 人民币）
   ↓
三层归因计算（汇率/合同/真本事）
   ↓
品类层归因（水/风/光 × 各国家）
   ↓
分公司层归因（三峡国际/长电国际/湖北能源）
   ↓
同比/环比双线对比
   ↓
异常检测（汇率/区域/合同/归因）
   ↓
文本生成（按 15.7 语言模式）
   ↓
输出模板渲染（按 15.8 输出模板）
   ↓
勾稽验证
   ↓
报告输出
```

#### 15.9.2 数据采集（国际段特有）

```yaml
data_sources:
  - source: 集团周报 Excel
    sheet: 综合分析表（国际段，Rows 39-74）
    fields: [volume, local_price, currency]
  
  - source: 汇率 API
    frequency: 每日
    format: API
    fields: [CNY_BRL, CNY_USD, CNY_EUR, ...]
  
  - source: 容量电价合同台账
    frequency: 合同变更时
    fields: [contract_name, price_fen, effective_date]
  
  - source: 各国家电力市场数据
    frequency: 每周
    fields: [local_spot_price, local_long_term_price]
```

#### 15.9.3 核心计算引擎

```python
def analyze_international_price(data: InternationalData) -> InternationalReport:
    # 1. 汇率折算
    cny_prices = convert_local_to_cny(data)
    
    # 2. 三层归因
    three_layer = three_layer_attribution(
        cny_prices.current,
        cny_prices.last_year,
        data.exchange_rates,
        data.contracts
    )
    
    # 3. 品类层归因（真本事的二级分解）
    category_breakdown = category_attribution(data)
    
    # 4. 分公司层归因
    company_breakdown = company_attribution(data)
    
    # 5. 同比环比双线对比
    yoy_mom_comparison = compare_yoy_mom(three_layer, category_breakdown)
    
    # 6. 异常检测
    anomalies = detect_international_anomalies(three_layer, data)
    
    # 7. 文本生成
    yoy_text = generate_yoy_text(three_layer, category_breakdown, company_breakdown)
    mom_text = generate_mom_text(three_layer, category_breakdown, company_breakdown)
    
    # 8. 勾稽验证
    validate(three_layer, category_breakdown, company_breakdown)
    
    return InternationalReport(
        yoy_text=yoy_text,
        mom_text=mom_text,
        yoy_mom_comparison=yoy_mom_comparison
    )
```

#### 15.9.4 模板引擎示例（国际段）

```python
INTERNATIONAL_TEMPLATES = {
    'yoy_intro': """
    {period}，集团公司国际上网电价约每千瓦时 {price_cny} 元，
    同比提高 {yoy_fen} 分
    {considerations_clause}。
    """,
    
    'yoy_attribution': """
    同比提高 {yoy_fen} 分，主要外币汇率变动
    （{currency_1} {yoy_pct_1}、{currency_2} {yoy_pct_2}、{currency_3} {yoy_pct_3}）
    影响度电均价提高 {exchange_fen} 分、
    {contract_name}容量电价变动影响度电均价提高 {contract_fen} 分；
    排除汇率、{contract_name}容量价格变动影响后，
    同比提高度电约 {real_fen} 分，
    汇率、{contract_name}容量价格以外的主要原因是 {reasons}。
    """,
    
    'category_attribution': """
    一是各区域 {category}量价变动影响国际度电均价 {direction} 约 {fen} 分：
    - {country} {category} {volume_desc}、{price_desc}，
      影响国际度电均价 {direction} 约 {country_fen} 分；
    - {country_2} {category} {description_2}，
      影响国际度电均价 {direction} 约 {country_2_fen} 分。
    """
}
```

#### 15.9.5 校验规则（国际段特有）

```python
# 1. 三层归因合计 = 总变化
assert abs(sum_three_layer - total_change) < 0.01

# 2. 品类层归因合计 = 真本事
assert abs(sum_categories - real_business_effect) < 0.01

# 3. 分公司影响合计 = 总变化
assert abs(sum_companies - total_change) < 0.05

# 4. 汇率影响 = ∑(基期当地价 × 国家电量 × 汇率变化)
assert abs(computed_exchange - expected_exchange) < 0.05

# 5. 收入勾稽（人民币口径）
for country in countries:
    expected = country.volume_yi_kwh * country.avg_price_cny * 1e8 / 1e8
    assert abs(expected - country.revenue_yi) < 0.1

# 6. 排除汇率/合同后真本事必须为非负（除非存在负向业务事件）
# 注：允许为负，但需要归因分析
```

#### 15.9.6 数据缺失处理

| 场景 | 处理方式 |
|---|---|
| 某国家数据缺失 | 用区域均值填充 + 标记"待补充" |
| 汇率数据缺失 | 用最近 5 日均价填充 + 标记"估算" |
| 容量电价合同数据缺失 | 跳过合同层归因 + 标记"未纳入" |
| 同比基期某国家数据缺失 | 跳过该国家同比 + 标记"基期缺失" |
| 多国家同时缺失 | 触发人工审核 |

---

### 15.10 实施优先级（国际段）

#### Phase 1（基础）
- [x] 国际总量（量、价、收入）
- [x] 同比、环比基础计算
- [x] 三层归因（汇率/合同/真本事）核心公式
- [x] 3 大运营主体数据接入（三峡国际/长电国际/湖北能源）

#### Phase 2（详细）
- [x] 5 区域 × 3 品类二维分析
- [x] 各国家原始数据采集 + 汇率折算
- [x] 同比/环比双线对比框架
- [x] 异常检测（汇率/区域/合同）
- [x] 语言模板 + 输出模板

#### Phase 3（高级）
- [ ] 多周趋势分析
- [ ] 汇率波动预测
- [ ] 项目级深度归因
- [ ] 地缘政治风险预警
- [ ] 跨年度汇率对冲建议

#### Phase 4（智能化）
- [ ] 自动识别汇率异常并提示对冲
- [ ] 区域风险自动评级
- [ ] 合同优化建议
- [ ] 海外资产组合优化

---

### 15.11 国际段关键提示词库

#### 15.11.1 关键术语对照

| 全称 | 简称 | 说明 |
|---|---|---|
| 三峡国际 | 三峡国际 | 三峡集团国际业务平台 |
| 长电国际 | 长电国际 | 长江电力国际业务平台 |
| 湖北能源 | 湖北能源 | 湖北能源国际业务 |
| 巴西雷亚尔 | 雷亚尔 / BRL | 巴西货币 |
| 容量电价 | 容量费 | 火电/特殊合同"待命"补贴 |
| 卡洛特 | Karot | 巴基斯坦水电项目 |
| Arinos | 阿利诺斯 | 巴西新投产光伏项目 |
| 度电均价 | 度电 | 总收入 ÷ 总电量 |
| 内生增长 | 真本事 | 排除汇率/合同后的真实经营能力 |

#### 15.11.2 常见数据问题

| 问题 | 表现 | 处理 |
|---|---|---|
| 币种混淆 | 度电单位不统一 | 强制双口径（当地 + 人民币）|
| 汇率滞后 | 用历史汇率折算 | 用报告日汇率 |
| 合同漏报 | 容量电价未纳入 | 合同台账与采集器联动 |
| 国家数据缺失 | 某些国家本周没数 | 区域均值填充 + 标记 |

---

## 16. 市场化交易分析框架

> 本节定义"**市场化交易**"分析的**数据模型、归因公式、板块模板、策略库**。
> 与第 15 节"国际电价"并列，覆盖周报"**二、3 市场化交易情况**"全部分析。
> 关键差异：市场化交易是"**基本盘 + 套利增量**"的双层结构，比"国内/国际电价"更复杂。

### 16.1 数据模型

#### 16.1.1 顶层数据字段

```json
{
  "report_id": "2026_W21_001",
  "market_trading": {
    "hydro": {
      "avg_price_yuan_per_kwh": 0.304,
      "yoy_price_change_fen": 1.3,
      "mom_price_change_fen": -0.35,
      "yoy_volume_yi_kwh": 9.5,
      "mom_volume_yi_kwh": 9.7,
      "spot_income_fen": 0.37,
      "spot_income_yi": 0.0534
    },
    "renewables": {
      "avg_price_yuan_per_kwh": 0.266,
      "yoy_price_change_fen": -1.6,
      "mom_price_change_fen": 1.3,
      "provinces_count": 28,
      "spot_provinces_count": 23
    },
    "thermal": {
      "avg_price_yuan_per_kwh": 0.402,
      "yoy_price_change_fen": -2.8,
      "mom_price_change_fen": 4.6,
      "units_operating": 4,
      "spot_price_yuan": 0.1710,
      "spot_price_yoy_pct": -31.71
    }
  },
  "by_strategy": {
    "aggressive_low_holding": ["山东"],
    "defensive_high_holding": ["湖北"],
    "regulatory_line_play": ["陕西"]
  }
}
```

#### 16.1.2 关键字段：策略维度

```json
{
  "strategy": {
    "type": "low_holding_aggressive",  // / high_holding_defensive / regulatory_line
    "long_term_position_pct": 30,  // 中长期持仓比例
    "spot_position_pct": 70,
    "trigger": "阴雨天气→光伏少→现货价高",
    "expected_income_fen": 4.6,
    "risk": "现货价不如预期"
  }
}
```

#### 16.1.3 必填字段检查清单（市场化交易段）

- [ ] 三大板块均价（0.304 / 0.266 / 0.402）
- [ ] 三大板块同比 + 环比
- [ ] 现货市场关键价格（南方、湖北）
- [ ] 上周 + 上上周的现货增收对比
- [ ] 关键电站成交电量（溪右、乌东德）
- [ ] 火电在运机组状态
- [ ] 系统负荷/风电/光伏/水电出力变化

---

### 16.2 计算公式

#### 16.2.1 现货增收核心公式

```python
def spot_income(volume_yi_kwh, spot_premium_fen):
    """
    现货增收 = 成交量 × 较中长期溢价
    """
    # volume_yi_kwh 单位：亿千瓦时
    # spot_premium_fen 单位：分/度
    return volume_yi_kwh * 1e8 * spot_premium_fen / 100 / 1e4  # 单位：万元


# 示例：本周水电现货增收
print(spot_income(9.7, 0.6))  # 582 万元（粗算）
# 实际 534 万元（考虑了 D-2 增发等其他因素）
```

#### 16.2.2 欠发套利公式（核心 ⭐）

```python
def underperform_arbitrage(
    base_price_fen,  # 基期度电
    current_volume_yi_kwh,  # 本期实际电量
    base_volume_yi_kwh,  # 基期电量
    capacity_fee_total_yi  # 容量费总额
):
    """
    欠发套利 = 容量费分摊变化 + 现货高价时段发电收益
    """
    # 度电容量电费变化
    capacity_fee_per_kwh_change_fen = (
        capacity_fee_total_yi / current_volume_yi_kwh -
        capacity_fee_total_yi / base_volume_yi_kwh
    ) * 100  # 分/度
    
    # 现货高价时段发电
    spot_premium_fen = base_price_fen * 0.02  # 假设现货高 2%
    
    total_effect_fen = capacity_fee_per_kwh_change_fen + spot_premium_fen
    return total_effect_fen


# 验算：火电同比 -2.8 分
# 中长期 -3 分 + 容量电费 +0.2 分 ≈ -2.8 ✅
```

#### 16.2.3 一省一价加权平均

```python
def weighted_avg_price_by_province(province_prices, province_volumes):
    """
    集团新能源加权均价
    """
    weighted_sum = sum(
        p["price_fen"] * p["volume_yi_kwh"] 
        for p in province_prices
    )
    total_volume = sum(p["volume_yi_kwh"] for p in province_prices)
    return weighted_sum / total_volume
```

#### 16.2.4 同比环比方向反转检测

```python
def detect_direction_reversal(yoy_change, mom_change):
    """
    同比 vs 环比方向是否反转
    """
    if (yoy_change > 0 and mom_change < 0) or (yoy_change < 0 and mom_change > 0):
        return "方向反转"
    return "方向一致"
```

#### 16.2.5 勾稽验证

```python
# 现货价跌幅验算
def verify_spot_decline(spot_now, spot_last_week):
    decline_pct = (spot_last_week - spot_now) / spot_last_week * 100
    return abs(decline_pct - 31.71) < 0.01  # 本周 31.71%

# 现货增收验算
def verify_spot_income(volume_yi_kwh, premium_fen):
    return abs(volume_yi_kwh * premium_fen * 1e8 / 100 / 1e4 - 534) < 50  # 534 万
```

---

### 16.3 水电市场化分析模板

```yaml
hydro_market:
  typical_cascade: "长江干流梯级（三峡、葛洲坝、溪洛渡、向家坝、乌东德、白鹤滩）"
  participation_markets:
    - "国网跨省跨区中长期"
    - "南网跨省跨区中长期"
    - "南方区域现货市场"
  data_template:
    avg_price_yuan_per_kwh: 0.304
    yoy_price_change_fen: 1.3
    mom_price_change_fen: -0.35
    spot_income_fen: 0.37  # 本周
    spot_income_fen_last_week: 0.75  # 上上周
    spot_income_yi: 0.0534
    spot_income_yi_last_week: 0.112
    spot_volume_yi_kwh:
      total: 9.7
      xiluodu: 6.5
      wudongde: 3.2
    spot_price_yuan_per_kwh:
      total: 0.30
      xiluodu: 0.312
      wudongde: 0.277
    spot_premium_fen:
      total: 0.6
      xiluodu: 0.7
      wudongde: 0.2
    d2_increment_yi_kwh: 0.006
  
  analysis_triggers:
    - 现货增收环比变化 > ±30%
    - 现货均价变化 > ±10%
    - 同比 / 环比方向反转
  
  output_template: |
    长江干流梯级...平均交易电价 {price} 元/度，
    同比{yoy_dir} {yoy_fen} 分（{yoy_reason}），
    环比{mom_dir} {mom_fen} 分（{mom_reason}）。
    南方区域市场收益提高大水电市场化电量度电收益 {spot_fen} 分，
    上上周 {last_week_fen} 分。
```

---

### 16.4 新能源市场化分析模板

```yaml
renewables_market:
  full_market_entry: true  # 全面入市
  provinces_count: 28
  spot_provinces_count: 23
  data_template:
    avg_price_yuan_per_kwh: 0.266
    yoy_price_change_fen: -1.6
    mom_price_change_fen: 1.3
  
  by_province_strategy:
    shandong:
      mom_change_fen: 4.6
      strategy: "low_holding_aggressive"  # 进攻型
      long_term_position_pct: "<30"
      trigger: "阴雨→光伏少→现货价高"
      risk: "现货价不如预期"
    hubei:
      mom_change_fen: 1.2
      strategy: "high_holding_defensive"  # 防守型
      long_term_position_pct: 95
      trigger: "阴雨→水电多→现货价跌"
      risk: "中长期价低于预期"
    shaanxi:
      mom_change_fen: 0.6
      strategy: "regulatory_line_play"  # 规则型
      long_term_position_change: "120% → 105%"
      trigger: "避免 105% 卡线回收"
      risk: "规则严→卡线失败"
    qinghai:
      yoy_change_fen: -3.4
      trigger: "供需宽松 + 去年无现货今年有"
    xinjiang:
      yoy_change_fen: -11  # -0.11 元
      trigger: "供需宽松 + 外送价格走低"
  
  regulatory_constraints:
    shaanxi_105_rule:
      description: "中长期持仓 > 105% 部分按价差 1.05 倍回收"
      optimal_position: "≤ 105%"
  
  analysis_triggers:
    - 一省价格差距 > ±5 分
    - 全面入市政策影响
    - 单一省份持仓比例 > 105%
  
  output_template: |
    新能源...平均交易电价 {price} 元/度，
    同比{yoy_dir} {yoy_fen} 分，
    环比{mom_dir} {mom_fen} 分。
    主要原因：{key_provinces}等地交易电价{mom_dir}。
    【省份明细】
    - {p1}：{p1_change} 分，{p1_strategy}
    - {p2}：{p2_change} 分，{p2_strategy}
    - {p3}：{p3_change} 分，{p3_strategy}
```

---

### 16.5 火电市场化分析模板

```yaml
thermal_market:
  only_coal_in_market: true  # 仅燃煤
  participation_markets:
    - "湖北现货市场"
  data_template:
    avg_price_yuan_per_kwh: 0.402
    yoy_price_change_fen: -2.8
    mom_price_change_fen: 4.6
    long_term_price_yuan: 0.39
    long_term_yoy_change_fen: -3
    spot_price_yuan: 0.1710
    spot_price_yoy_pct: -31.71
    units_operating:
      - "鄂州#2"
      - "鄂州#3"
      - "鄂州#6"
      - "宜城#2"
  
  three_layer_attribution:
    long_term_effect_fen: -3
    spot_effect_fen: -0.0
    capacity_fee_effect_fen: 0.2
    net_effect_fen: -2.8  # 验算：-3 + 0.2 = -2.8 ✅
  
  system_data:
    system_load_change_wan_kw: 11
    wind_nm_change_wan_kw: 24
    solar_change_wan_kw: -326
  
  underperform_arbitrage:
    description: "现货价低 + 主动少发 + 容量电费保底"
    math:
      capacity_fee_per_kwh_old: X
      capacity_fee_per_kwh_new: Y  # Y > X（少发分摊变高）
    
  analysis_triggers:
    - 现货价跌幅 > ±20%
    - 度电容量电费分摊变化 > ±0.5 分
    - 同比 / 环比方向反转
    - 火电在运机组变化
  
  output_template: |
    火电...平均交易电价 {price} 元/度，
    同比{yoy_dir} {yoy_fen} 分（中长期{yoy_lt} {yoy_lt_fen} 分），
    环比{mom_dir} {mom_fen} 分（{mom_reason}）。
    【关键数据】
    - 现货价 {spot} 元（环比{spot_change_pct}%）
    - 在运机组：{units}
    - 现货跌 {spot_decline_pct}%，火电{mom_dir} {mom_fen} 分 = 少发多赚
```

---

### 16.6 三大板块对比模板

```python
THREE_BOARD_COMPARISON = {
    "hydro": {
        "yoy_change_fen": 1.3,
        "mom_change_fen": -0.35,
        "story": "能力涨、动能弱"
    },
    "renewables": {
        "yoy_change_fen": -1.6,
        "mom_change_fen": 1.3,
        "story": "能力退、动能反弹"
    },
    "thermal": {
        "yoy_change_fen": -2.8,
        "mom_change_fen": 4.6,
        "story": "能力退、动能最强反弹"
    }
}

def compare_three_boards():
    """
    输出同一周三种板块的不同故事
    """
    return "同一周多板块 = 东方不亮西方亮 = 抗周期能力"
```

---

### 16.7 异常检测规则

#### 16.7.1 现货增收异常

| 指标 | 阈值 | 触发动作 |
|---|---|---|
| 现货增收周变化 > ±30% | 触发 | 详细分析市场行情 |
| 现货增收周变化 > ±50% | **重点** | 高层关注市场突变 |

#### 16.7.2 一省一价异常

| 指标 | 阈值 | 触发动作 |
|---|---|---|
| 一省价格 vs 集团均价 > ±5 分 | 触发 | 详细分析 |
| 省份间价差 > ±8 分 | **重点** | 战略级本地化能力评估 |

#### 16.7.3 持仓异常

| 指标 | 阈值 | 触发动作 |
|---|---|---|
| 持仓比例 > 105% | 触发 | 监管回收风险预警 |
| 持仓变化 > ±20 pp（周）| 触发 | 调仓风险评估 |

#### 16.7.4 火电战略信号

| 指标 | 阈值 | 触发动作 |
|---|---|---|
| 同比 -2.8 / 环比 +4.6 反转 | 触发 | 标注"长期退 + 短期套利"双面性 |
| 在运机组 < 50% 总数 | 提示 | 战略性退场预警 |
| 现货价跌幅 > ±30% | **重点** | 欠发套利机会/风险提示 |

#### 16.7.5 归因异常

| 指标 | 阈值 | 触发动作 |
|---|---|---|
| 容量电费对冲 > 中长期下行 50% | 触发 | 标注"对冲有效性" |
| 现货增收占度电比例 > 30% | **重点** | 现货依赖度过高 |

---

### 16.8 语言模式库

#### 16.8.1 水电话术

```
水电项目：[电站列表]...平均交易电价约为每千瓦时 {price} 元，
[同比/环比] [提高/降低] 约每千瓦时 {change} 分，
主要原因是 [结构原因] 以及 [电站] 参与 [市场] 现货增收 [提高/降低]。
（南方区域市场收益提高大水电市场化电量度电收益约每千瓦时 {spot_fen} 分，
上上周提高约每千瓦时 {last_week_fen} 分）
（上周，集团公司大水电参与 [市场] 日前成交电量 {volume} 亿千瓦时，
[电站 A] {vol_a} 亿，[电站 B] {vol_b} 亿，
较 D-2 中长期电量增发 {inc} 亿。
日前市场结算均价 {spot} 元，
较中长期高 {premium} 分，较非现货环境预计增收约 {income} 万元，
上上周增收约 {last_income} 万元。）
```

#### 16.8.2 新能源话术

```
新能源项目（参与 {N} 个省（区、市）市场交易，
包括 [省份列表] 等 {M} 个省区现货市场）平均交易电价为每千瓦时 {price} 元，
[同比/环比] [降低/提高] 每千瓦时 {change} 分，
主要原因是 [整体原因 / 省份原因]。
（[省份 A]：[变化] 分，主要原因是 [触发原因]）...
```

#### 16.8.3 火电话术

```
火电项目目前仅燃煤机组参与市场交易，
参与 [省份] 现货市场，平均交易电价为每千瓦时 {price} 元，
[同比/环比] [下降/提高] 每千瓦时 {change} 分，
主要原因是 [原因]（上周中长期合同每千瓦时 {lt} 元，
[同比/环比] [下降/提高] 每千瓦时 {lt_change} 元）。
[关键数据]
（平均系统负荷、风电及非市场机组出力分别上升/下降 X、Y 及 Z 万千瓦，
[电源] 增加/减少 W 万千瓦，
[省份] 上周现货市场均价每千瓦时 {spot} 元，
上上周每千瓦时 {last_spot} 元，环比下降/上升 {decline_pct}%。）
```

---

### 16.9 输出格式模板

#### 16.9.1 水电段输出

```markdown
水电项目：长江干流梯级电站（主要参与国网、南网跨省跨区中长期交易，
南方区域现货市场交易）平均交易电价约为每千瓦时 0.304 元，
同比提高约每千瓦时 1.3 分（主要原因为电量结构性变化以及溪右、乌东德电站
参与南方区域现货增收提高）。环比降低约每千瓦时 0.35 分，
主要原因是溪右、乌东德参与南方区域现货电费增收环比降低。
（南方区域市场收益提高大水电市场化电量度电收益约每千瓦时 0.37 分，
上上周提高约每千瓦时 0.75 分）
（上周，集团公司大水电参与南方区域电力市场日前成交电量 9.7 亿千瓦时
（溪右 6.5 亿千瓦时，乌东德 3.2 亿千瓦时），
较 D-2 中长期电量增发 0.006 亿千瓦时。
日前市场结算均价每千瓦时 0.30 元
（溪右每千瓦时 0.312 元，乌东德每千瓦时 0.277 元），
较中长期高每千瓦时 0.6 分（溪右高每千瓦时 0.7 分，乌东德高每千瓦时 0.2 分），
较非现货环境预计增收约 534 万元，上上周增收约 1120 万元。）
```

#### 16.9.2 新能源段输出

```markdown
新能源项目（参与 28 个省（区、市）市场交易...）平均交易电价为每千瓦时 0.266 元，
同比降低每千瓦时 1.6 分...
环比提高每千瓦时 1.3 分，主要原因是山东、湖北、陕西等地交易电价提高。
（山东：交易电价环比提高每千瓦时 4.6 分...）
（湖北：交易电价环比提高每千瓦时 1.2 分...）
（陕西：交易电价环比提高每千瓦时 0.6 分...）
```

#### 16.9.3 火电段输出

```markdown
火电项目目前仅燃煤机组参与市场交易，参与湖北省现货市场，
平均交易电价为每千瓦时 0.402 元，
同比下降每千瓦时 2.8 分...环比提高每千瓦时 4.6 分...
上周鄂州 #2、#3、#6，宜城 #2 在运。
（平均系统负荷、风电及非市场机组出力分别上升 11 万、24 万及 229 万千瓦，
光伏减少 326 万千瓦，
湖北省上周现货市场均价每千瓦时 0.1710 元，
上上周每千瓦时 0.2503 元，环比下降 31.71%。）
```

---

### 16.10 自动化数据流

#### 16.10.1 整体流程

```
数据采集
   ↓
三大板块数据分流（水电/新能源/火电）
   ↓
水电：现货增收、电站拆分、勾稽
   ↓
新能源：省份策略识别、价差分析
   ↓
火电：欠发套利、容量电费对冲、机组状态
   ↓
三大板块对比
   ↓
异常检测（现货/省份/持仓/火电战略）
   ↓
文本生成（按 16.8 语言模式）
   ↓
输出模板渲染（按 16.9 输出模板）
   ↓
勾稽验证
   ↓
报告输出
```

#### 16.10.2 核心计算引擎

```python
def analyze_market_trading(data: MarketTradingData) -> MarketTradingReport:
    # 1. 三大板块基础计算
    hydro_metrics = calculate_hydro_metrics(data.hydro)
    renewables_metrics = calculate_renewables_metrics(data.renewables)
    thermal_metrics = calculate_thermal_metrics(data.thermal)
    
    # 2. 同比环比
    hydro_yoy_mom = calculate_yoy_mom(hydro_metrics)
    renewables_yoy_mom = calculate_yoy_mom(renewables_metrics)
    thermal_yoy_mom = calculate_yoy_mom(thermal_metrics)
    
    # 3. 板块特有分析
    spot_arbitrage = analyze_spot_arbitrage(data)  # 水电
    province_strategy = identify_strategy(data.renewables)  # 新能源
    underperform_arbitrage = analyze_underperform(data.thermal)  # 火电
    
    # 4. 三大板块对比
    three_boards = compare_three_boards(
        hydro_yoy_mom, renewables_yoy_mom, thermal_yoy_mom
    )
    
    # 5. 异常检测
    anomalies = detect_market_anomalies(
        hydro_metrics, renewables_metrics, thermal_metrics
    )
    
    # 6. 文本生成
    hydro_text = generate_hydro_text(hydro_metrics, spot_arbitrage)
    renewables_text = generate_renewables_text(renewables_metrics, province_strategy)
    thermal_text = generate_thermal_text(thermal_metrics, underperform_arbitrage)
    
    # 7. 勾稽验证
    validate(spot_arbitrage, underperform_arbitrage)
    
    return MarketTradingReport(
        hydro=hydro_text,
        renewables=renewables_text,
        thermal=thermal_text,
        three_boards_comparison=three_boards
    )
```

---

### 16.11 实施优先级

#### Phase 1（基础）
- [x] 三大板块均价 + 同比环比
- [x] 现货市场关键价格采集
- [x] 火电在运机组状态
- [x] 系统负荷/风电/光伏/水电出力变化

#### Phase 2（详细）
- [x] 现货增收核心公式 + 验算
- [x] 省份策略识别（高/低持仓/卡线）
- [x] 欠发套利公式 + 容量电费对冲
- [x] 三大板块对比

#### Phase 3（高级）
- [ ] 多周现货增收趋势分析
- [ ] 省份策略效果回测
- [ ] 火电欠发套利预警
- [ ] 自动识别监管规则变化

#### Phase 4（智能化）
- [ ] 机器学习预测现货价
- [ ] 策略组合优化
- [ ] 异常根因自动归因
- [ ] 行业对标

---

### 16.12 关键术语库（市场化交易段）

| 全称 | 简称 | 关键数据 |
|---|---|---|
| 中长期合同 | 中长期 | 1-3 年锁价 |
| 现货市场 | 现货 | 实时定价 |
| D-2 | D-2 | 提前 2 天 |
| 日前市场 | 日前 | 提前 1 天 |
| 较 D-2 中长期电量增发 | D-2 增发 | 现货增量 |
| 现货增收 | 现货增收 | 套利金额 |
| 度电容量电费 | 度电容量费 | 单位分/度 |
| 欠发套利 | 欠发 | 少发多赚 |
| 全面入市 | 全面入市 | 政策概念 |
| 持仓比例 | 持仓 | 中长期占比 |
| 卡线 | 卡线 | 105% 监管线 |
| 价差回收 | 回收 | 1.05 倍 |
| 一省一策 | 一省一策 | 本地化运营 |

---

## 17. 环境资产分析框架（绿证 + CCER）

> 本节定义"**环境资产**"（绿证 + CCER）分析的**数据模型、价格信号、库存管理、自动化流程**。
> 覆盖周报"**二、（二）绿证、CCER 核发交易情况**"段。
> 这是"**第四类业务**"——区别于传统发电、售电、投资的轻资产业务。

### 17.1 数据模型

#### 17.1.1 顶层数据字段

```json
{
  "report_id": "2026_W21_001",
  "environmental_assets": {
    "green_cert": {
      "weekly_issued_wan": 12.4,
      "weekly_sold_wan": 3.0,
      "yoy_cumulative_sold_wan": 448.0,
      "yoy_cumulative_avg_price": 4.7,
      "inventory_wan": {
        "2026": 330,
        "2025": 767,
        "2024": 66,
        "total": 1163
      }
    },
    "ccer": {
      "weekly_sold_tons": 2100,
      "weekly_avg_price": 85,
      "yoy_cumulative_sold_wan_tons": 43.4,
      "yoy_cumulative_avg_price": 83.7,
      "inventory_wan_tons": 506
    }
  }
}
```

#### 17.1.2 绿证按年份细分

```json
{
  "green_cert_by_year": {
    "2026": {
      "weekly_sold_count": 472,
      "weekly_avg_price": 8.1,
      "mom_price_change": -0.4,
      "inventory_wan": 330
    },
    "2025": {
      "weekly_sold_count": 29000,
      "weekly_avg_price": 4.5,
      "inventory_wan": 767
    },
    "2024": {
      "inventory_wan": 66
    }
  }
}
```

#### 17.1.3 必填字段检查清单（环境资产段）

- [ ] 本周核发绿证数
- [ ] 本周销售绿证数（按年份拆分）
- [ ] 本周销售 CCER 减排量
- [ ] 绿证库存（按年份）
- [ ] CCER 库存
- [ ] 累计销售（年度）
- [ ] 均价（本周 + 累计）

---

### 17.2 计算公式

#### 17.2.1 销售金额计算

```python
def green_cert_revenue(quantity, avg_price):
    """绿证销售金额（单位：万元）"""
    return quantity * avg_price / 10000  # 个 → 万元


def ccer_revenue(tons, avg_price):
    """CCER 销售金额（单位：万元）"""
    return tons * avg_price / 10000  # 元 → 万元


# 验算：本周绿证
# 2025: 2.9 万 × 4.5 = 13.05 万元
# 2026: 472 × 8.1 = 0.38 万元
# 合计：13.43 万元 ✅
print(green_cert_revenue(29000, 4.5) + green_cert_revenue(472, 8.1))

# 验算：本周 CCER
# 2100 × 85 = 17.85 万元 ✅
print(ccer_revenue(2100, 85))
```

#### 17.2.2 库存估值

```python
def inventory_value(quantity, est_price):
    """
    库存估值（单位：万元）
    """
    return quantity * est_price / 10000


# 绿证库存
green_cert_value = (
    330 * 8.1 +   # 2026
    767 * 4.5 +   # 2025
    66 * 4         # 2024 估
) / 10000  # = 6389 万元

# CCER 库存
ccer_value = 506 * 10000 * 85 / 10000  # = 4301 万元

# 合计
total = green_cert_value + ccer_value  # ≈ 1.07 亿元
```

#### 17.2.3 价差检测

```python
def price_premium_pct(price_new, price_old):
    """稀缺性溢价百分比"""
    return (price_new - price_old) / price_old * 100


# 验算：2026 绿证 vs 2025 绿证
# (8.1 - 4.5) / 4.5 = 80% ✅
print(price_premium_pct(8.1, 4.5))
```

---

### 17.3 绿证分析模板

```yaml
green_cert_analysis:
  unit: "个/张"
  conversion: "1 张 = 1 兆瓦时 = 1,000 度"
  
  data_template:
    weekly_issued_wan: 12.4
    weekly_sold_wan: 3.0
    by_year:
      "2025":
        sold_wan: 2.9
        avg_price: 4.5
      "2026":
        sold_count: 472
        avg_price: 8.1
        mom_change: -0.4
    yoy_cumulative:
      sold_wan: 448.0
      avg_price: 4.7
    inventory_wan:
      "2026": 330
      "2025": 767
      "2024": 66
      total: 1163
  
  key_findings:
    price_premium:
      "2026_vs_2025": 80%  # 8.1 vs 4.5
      reason: "稀缺性溢价"
    price_warning:
      "2026_mom": -0.4
      reason: "稀缺品种开始降价"
  
  analysis_triggers:
    - 当年新发绿证均价 - 累计均价 > ±30%
    - 库存结构：老绿证 > 50%
    - 环比价格变化 > ±5%
  
  output_template: |
    上周，集团公司核发绿证 {issued} 万个；
    销售绿证 {sold} 万个，
    交易均价每个 {avg_price} 元，
    其中 2025 年绿证 {sold_2025} 万个，
    交易均价每个 {price_2025} 元；
    2026 年绿证 {sold_2026} 个，
    交易均价每个 {price_2026} 元，环比 {mom_dir} {mom_change} 元。
    2026 年内累计销售绿证 {cumulative_sold} 万个，
    销售均价每个 {cumulative_avg} 元。
    截至目前，集团公司持有可交易绿证 {inventory} 万个
    （包括 2026 年 {inv_2026} 万个，
    2025 年 {inv_2025} 万个、
    2024 年 {inv_2024} 万个）。
```

---

### 17.4 CCER 分析模板

```yaml
ccer_analysis:
  unit: "吨"
  conversion: "1 吨 = 1 吨 CO2 减排"
  
  data_template:
    weekly_sold_tons: 2100
    weekly_avg_price: 85
    yoy_cumulative:
      sold_wan_tons: 43.4
      avg_price: 83.7
    inventory_wan_tons: 506
  
  key_findings:
    weekly_revenue_wan: 17.85
    cumulative_revenue_wan: 363.26
    inventory_value_wan: 4301
  
  analysis_triggers:
    - CCER 均价变化 > ±10%
    - 库存量同比变化 > ±30%
    - 累计销售同比变化 > ±50%
  
  output_template: |
    上周，集团公司销售 CCER 项目减排量 {weekly_sold} 吨，
    交易均价每吨 {weekly_price} 元。
    2026 年集团公司累计销售 CCER 项目减排量 {cumulative_sold} 万吨，
    销售均价每吨 {cumulative_price} 元。
    截止目前，集团公司 CCER 项目减排量库存量 {inventory} 万吨。
```

---

### 17.5 价格信号与库存分析

#### 17.5.1 关键发现检测

```python
def detect_findings(green_cert_data, ccer_data):
    findings = []
    
    # 发现 1：2025 vs 2026 价差
    if green_cert_data["2026_price"] > green_cert_data["2025_price"] * 1.5:
        findings.append({
            "type": "price_premium",
            "msg": f"2026 绿证比 2025 贵 {price_premium_pct(green_cert_data['2026_price'], green_cert_data['2025_price']):.0f}%"
        })
    
    # 发现 2：环比降价预警
    if green_cert_data["2026_mom"] < 0:
        findings.append({
            "type": "price_warning",
            "msg": f"2026 绿证环比 {green_cert_data['2026_mom']} 元（警惕降价）"
        })
    
    # 发现 3：库存结构
    if green_cert_data["inventory"]["2024"] / green_cert_data["inventory"]["total"] > 0.1:
        findings.append({
            "type": "inventory_age",
            "msg": "老绿证（2024）占比超 10%，可能贬值"
        })
    
    return findings
```

#### 17.5.2 库存估值表

| 资产 | 数量 | 估值单价 | 估值（万元）|
|------|------|---------|-----------|
| 2026 绿证 | 330 万 | 8.1 元 | 2,673 |
| 2025 绿证 | 767 万 | 4.5 元 | 3,452 |
| 2024 绿证 | 66 万 | 4.0 元（估）| 264 |
| **绿证小计** | **1,163 万** | — | **6,389** |
| **CCER 库存** | **506 万吨** | 85 元 | **4,301** |
| **合计** | — | — | **10,690** ⭐ |

---

### 17.6 异常检测规则

#### 17.6.1 价格异常

| 指标 | 阈值 | 触发动作 |
|---|---|---|
| 当年新发绿证均价 - 老绿证 > 50% | 触发 | 稀缺性溢价提示 |
| 当年新发绿证环比变化 < -5% | 触发 | 降价预警 |
| CCER 均价周变化 > ±15% | 触发 | 详细分析市场行情 |

#### 17.6.2 库存异常

| 指标 | 阈值 | 触发动作 |
|---|---|---|
| 老绿证（>1 年）库存占比 > 30% | **重点** | 减值风险预警 |
| CCER 库存量同比 < -30% | 触发 | 库存告急 |
| 累计销售同比 > 100% | 提示 | 业务高速增长 |

#### 17.6.3 业务异常

| 指标 | 阈值 | 触发动作 |
|---|---|---|
| 本周销售 < 累计周均 50% | 触发 | 业务下滑 |
| 新发绿证 - 销售 > 5 倍 | 提示 | 库存积累过快 |

---

### 17.7 语言模式库

#### 17.7.1 绿证话术

```
上周，集团公司核发绿证 {issued} 万个；
销售绿证 {sold} 万个，
交易均价每个 {avg_price} 元，
其中 2025 年绿证 {sold_2025} 万个，
交易均价每个 {price_2025} 元；
2026 年绿证 {sold_2026} 个，
交易均价每个 {price_2026} 元，
环比 {mom_dir} {mom_change} 元。
2026 年内累计销售绿证 {cumulative_sold} 万个，
销售均价每个 {cumulative_avg} 元。
截至目前，集团公司持有可交易绿证 {inventory} 万个
（包括 2026 年 {inv_2026} 万个，
2025 年 {inv_2025} 万个、
2024 年 {inv_2024} 万个）。
```

#### 17.7.2 CCER 话术

```
上周，集团公司销售 CCER 项目减排量 {weekly_sold} 吨，
交易均价每吨 {weekly_price} 元。
2026 年集团公司累计销售 CCER 项目减排量 {cumulative_sold} 万吨，
销售均价每吨 {cumulative_price} 元。
截止目前，集团公司 CCER 项目减排量库存量 {inventory} 万吨。
```

---

### 17.8 输出格式模板

#### 17.8.1 绿证段输出

```markdown
上周，集团公司核发绿证 12.4 万个；
销售绿证 3.0 万个，
交易均价每个 4.5 元，
其中 2025 年绿证 2.9 万个，
交易均价每个 4.5 元；
2026 年绿证 472 个，
交易均价每个 8.1 元，环比下降 0.4 元。
2026 年内累计销售绿证 448.0 万个，
销售均价每个 4.7 元。
截至目前，集团公司持有可交易绿证 1163 万个
（包括 2026 年 330 万个，
2025 年 767 万个、
2024 年 66 万个）。
```

#### 17.8.2 CCER 段输出

```markdown
上周，集团公司销售 CCER 项目减排量 2100 吨，
交易均价每吨 85 元。
2026 年集团公司累计销售 CCER 项目减排量 43.4 万吨，
销售均价每吨 83.7 元。
截止目前，集团公司 CCER 项目减排量库存量 506 万吨。
```

---

### 17.9 自动化数据流

#### 17.9.1 整体流程

```
绿证/CCER 数据采集
   ↓
按年份分类（2024/2025/2026）
   ↓
价格信号识别（稀缺性溢价、环比变化）
   ↓
库存结构分析（年份占比）
   ↓
库存估值（按当前/历史价格）
   ↓
异常检测（价格/库存/业务）
   ↓
文本生成（按 17.7 语言模式）
   ↓
输出模板渲染（按 17.8 输出模板）
   ↓
勾稽验证
   ↓
报告输出
```

#### 17.9.2 核心计算引擎

```python
def analyze_environmental_assets(data: EnvironmentalAssetsData) -> EnvAssetsReport:
    # 1. 销售金额计算
    green_cert_revenue = calculate_green_cert_revenue(data.green_cert)
    ccer_revenue = calculate_ccer_revenue(data.ccer)
    
    # 2. 库存估值
    inventory_value = estimate_inventory_value(data)
    
    # 3. 价格信号
    price_signals = detect_price_signals(data.green_cert, data.ccer)
    
    # 4. 库存结构分析
    inventory_structure = analyze_inventory_structure(data.green_cert)
    
    # 5. 异常检测
    anomalies = detect_env_assets_anomalies(data)
    
    # 6. 文本生成
    green_cert_text = generate_green_cert_text(data)
    ccer_text = generate_ccer_text(data)
    
    return EnvAssetsReport(
        green_cert=green_cert_text,
        ccer=ccer_text,
        price_signals=price_signals,
        inventory_value=inventory_value
    )
```

---

### 17.10 实施优先级

#### Phase 1（基础）
- [x] 绿证本周销售（按年份）
- [x] CCER 本周销售
- [x] 库存量（按年份）
- [x] 累计销售 + 均价

#### Phase 2（详细）
- [x] 价格信号识别（2025 vs 2026 价差）
- [x] 库存结构分析
- [x] 库存估值
- [x] 异常检测规则

#### Phase 3（高级）
- [ ] 多周趋势分析
- [ ] 价格预测模型
- [ ] 最佳出售时机建议
- [ ] 政策变化影响评估

#### Phase 4（智能化）
- [ ] 碳市场扩容预期建模
- [ ] 自动化交易策略
- [ ] 跨市场套利检测
- [ ] 行业对标分析

---

### 17.11 关键术语库（环境资产段）

| 全称 | 简称 | 关键数据 |
|---|---|---|
| 绿色电力证书 | 绿证 | 1 张 = 1,000 度绿电 |
| 中国核证自愿减排量 | CCER | 1 吨 = 1 吨 CO2 减排 |
| 核发 | 核发 | 政府/机构发放 |
| 销售 | 销售 | 集团卖出 |
| 库存 | 库存 | 持有未售 |
| 累计销售 | 累计 | 一年内总计 |
| 交易均价 | 均价 | 平均售价 |
| 2024/2025/2026 绿证 | 按年份 | 不同批次 |
| 稀缺性溢价 | 稀缺溢价 | 新发高价 |
| 第四类业务 | 第四类 | 区别于发电/售电/投资 |
| 库存估值 | 估值 | 隐含价值 |
| 轻资产业务 | 轻资产 | 毛利率 ~100% |

---

## 18. 版本历史

| 版本 | 日期 | 说明 |
|---|---|---|
| v1.0 | 2026-06-05 | 初版，基于 5 月 22 日周报分析整理 |
| v1.1 | 2026-06-05 | 新增第 15 节：国际电价分析框架，覆盖数据模型（汇率/国家/品类/合同）、三层归因公式（汇率/合同/真本事）、5 区域模板、同比环比双线分析、异常检测、语言模式、输出模板、自动化数据流；文档扩展为国内+国际 |
| v1.2 | 2026-06-05 | 新增第 16 节（市场化交易分析框架：水电/新能源/火电，含现货增收、欠发套利、一省一策、3 大板块对比）和第 17 节（环境资产分析框架：绿证/CCER，含价差怪现象、库存估值、第四类业务），文档扩展为国内+国际+市场化+环境资产全场景 |

---

> 📝 **开发者注**：本框架基于实际周报分析逻辑整理，目标是**让自动化生成的周报**达到人工分析的**80%** 水平。
>
> 关键成功因素：
> 1. **数据准确** —— 自动化前提
> 2. **模板完整** —— 覆盖所有场景
> 3. **异常检测** —— 防止错误输出
> 4. **勾稽验证** —— 保证可信度
>
> 后续迭代方向：多周对比、预测模型、智能化归因。
>
> —— 来自"周报自动化项目"组
