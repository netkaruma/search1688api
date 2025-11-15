# 1688 以图搜货 API

Python 库，用于通过图片在 1688.com 上搜索商品。
以及通过 ID/货号 解析商品数据。

## 安装

```bash
pip install search1688api
```

## 使用方法

### 同步版本

```python
from search1688api import Sync1688Session

with Sync1688Session() as session:
    # 通过图片搜索
    products = session.search_by_image("path/to/image.jpg")
    for product in products:
        print(product.name)
        print(product.url)
        print(product.company)
        print(product.price)
    
    # 通过 ID 获取商品详细信息
    detailed_product = session.get_by_id("741375431874")
    if detailed_product:
        print(detailed_product.to_dict())
```

### 异步版本

```python
import asyncio
from search1688api import Async1688Session

async def main():
    async with Async1688Session() as session:
        # 通过图片搜索
        products = await session.search_by_image("path/to/image.jpg")
        for product in products:
            print(product.name)
            print(product.url)
            print(product.company)
            print(product.price)
        
        # 通过 ID 获取商品详细信息
        detailed_product = await session.get_by_id("741375431874")
        if detailed_product:
            print(detailed_product.to_dict())

asyncio.run(main())
```
## 超时设置
### 创建会话时设置

```python
# 默认超时 30 秒
session = Sync1688Session()

# 设置自定义超时
session = Sync1688Session(default_timeout=60)  # 60 秒
```

### 为单个请求设置
```python
# 使用默认超时
products = session.search_by_image("image.jpg")
detailed = session.get_by_id("123456")

# 为特定请求设置超时
products = session.search_by_image("image.jpg", timeout=10)  # 10 秒
detailed = session.get_by_id("123456", timeout=15)           # 15 秒
```
### 创建后修改超时
```python
session = Sync1688Session()
session.default_timeout = 45  # 现在所有请求超时时间为 45 秒
```
## Product 模型

## Product 类包含以下属性：
| 属性 | 类型 | 描述 |
|------------------|------------|---------------------------------------------------------------------------------------------------|
| id | str | 商品在 1688 上的唯一标识符 |
| name | str | 商品全名 |
| simple_name | str | 简化/缩写商品名称 |
| brief | str | 商品简要描述 |
| company | str | 卖家公司名称 |
| company_location | str | 卖家所在地区（省和市） |
| credit_level | str | 卖家信用等级（评分） |
| is_factory | bool | 卖家是否为工厂（True/False） |
| price | str | 商品主要价格 |
| quantity_prices | List[Dict] | 根据数量定价的列表。示例：[{"quantity": 2, "price": "¥10"}] |
| image_url | str | 商品主图片链接 |
| image_url_220x220 | str | 220x220 尺寸的图片链接 |
| booked_count | int | 已预订数量 |
| sale_quantity | int | 已售数量 |
| quantity_begin | int | 最小起订量 |
| url | str | 商品页面直接链接（https://detail.1688.com/offer/{id}.html） |
| category_id | int | 商品分类 ID |
| tags | List[str] | 标签标识符列表（市场标签、会员标签、节日标签等） |
| service_labels | List[str] | 活跃服务标签列表（例如，"快速发货"） |
| raw_data | Dict | 来自 JSON 响应的原始商品数据 |                                            |
## DetailProduct 类（通过 ID 解析）
| 属性 | 类型 | 描述 |
|--------------|----------|------------------------|
| id | str | 商品 ID |
| name | str | 商品名称 |
| brand | str | 商品品牌 |
| price | str | 价格 |
| company | str | 公司名称 |
| grade | str | 商品评分 |
| weight | str | 商品重量/体积 |
| goods | List[Dict] | 商品变体列表，包含价格和图片 |
| repeat_orders | str | 回头率 |
| saledCount | int | 销量 |
| raw_data | Dict | 来自 JSON 响应的原始商品数据 |

## 方法
```python
search_by_image(image_path: str, timeout: float = None) -> List[Product]
```

### 参数：
1. **image_path** - 图片文件路径
2. **timeout** - 请求超时时间（秒）（默认使用会话的 default_timeout)
### 返回：Product 对象列表

```python
get_by_id(offer_id: str, timeout: float = None) -> DetailProduct
```
### 通过商品 ID 获取详细信息。
### 参数：
1. **offer_id** - 商品在 1688.com 上的 ID
2. **timeout** - 请求超时时间（秒）（默认使用会话的 default_timeout）
### 返回：DetailProduct 对象，如果未找到商品则返回 None

## 转换为字典
```python
product_dict = product.to_dict()
detailed_product_dict = detailed_product.to_dict()
```

## 转换为字典示例
```python
product_dict = product.to_dict()
print(product_dict)
```

## 处理商品变体
```python
detailed_product = session.get_by_id("741375431874", timeout=30)
if detailed_product:
    for variant in detailed_product.goods:
        print(f"Вариант: {variant['name']}")
        print(f"Цена: {variant['price']}")
        print(f"Изображение: {variant['imageUrl']}")
```

## 访问aiohttp会话
```python
async with Async1688Session() as customSession:
    session = customSession.session
```

## 许可证

MIT
