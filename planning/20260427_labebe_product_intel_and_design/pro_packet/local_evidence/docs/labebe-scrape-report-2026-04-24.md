# labebeclub.com 产品数据抓取报告

**日期**: 2026-04-24
**操作**: 全站产品及图片抓取

## 数据概览

| 指标 | 数值 |
|------|------|
| 产品总数 | 46 |
| 图片总数 | 460（164.6 MB） |
| 平均价格 | $103.64 |
| 有折扣产品 | 8 |

## Collection 分布

| Collection | 产品数 |
|------------|--------|
| furniture | 17 |
| rockers-ride-ons | 13 |
| pretend-play | 9 |
| activity-educational-toys | 6 |
| new-in | 1 |

## 价格区间

- 最低: $33.99
- 最高: $179.99

## 输出文件

```
data/labebe/
├── labebe_products.csv              # 46产品，含本地图片路径
├── labebe_products_with_images.csv # 备份版本
├── all_product_images.json         # 459图片URL索引
└── images/                         # 460张图片
    ├── {slug}.jpg                  # 主图
    ├── {slug}_2.jpg                # 画廊图2
    └── ...
```

## 技术说明

### 抓取工具
- `scrape_labebe.py`: Playwright 抓取站点产品列表
- `all_product_images.json`: 各产品完整画廊URL索引

### 图片CDN
- 域名: `media.cdn.ishopastro.com`（Shopify/CDN）
- 格式: 全部为JPG，无WebP转换问题

### 曾遇到的问题
1. **Shopify CDN返回WebP但文件扩展名为.jpg**: 通过检测RIFF/WEBP文件头识别并处理
2. **21个产品图片下载失败**: 初次下载时部分网络超时，后全部重试成功
3. **TLS/SSL连接中断**: 1张图片需重试，最终460张全部完成

## 状态

✅ 完成 - 所有46产品、460张图片已验证完整
