# 1688 API 图片|文字搜索产品 

一个用于通过图片|文字在1688.com上搜索产品的Python库。

## 安装p

```bash
pip install search1688api
```

## 使用方法

### 同步版本

```python
from search1688api import Sync1688Session

with Sync1688Session(debug = False, proxy = proxy) as session:
    products = session.search_by_image("path/to/image.jpg")
    products = session.search_by_text("search query")
```

### 异步版本

```python
from search1688api import Async1688Session
import asyncio

async def main():

    async with Async1688Session(debug = False, proxies = proxies) as session:
        response = await session.search_by_image("path/to/image.jpg")
        response = await session.search_by_text("rose-colored glasses")
        
asyncio.run(main())
```

## 方法
```python
search_by_image(image_path: str, debug = True) -> List[]
search_by_text(image_path: str, debug = True) -> List[]
```

### 选项:
1. **image_path** - 图像文件路径
2. **debug** - 使用日志记录功能

## 许可证
MIT
