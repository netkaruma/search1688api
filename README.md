# 1688 API 图片|文字搜索产品 

一个用于通过图片|文字在1688.com上搜索产品的Python库。

## 安装

```bash
pip install search1688api
```

## 使用方法

### 同步版本

```python
from search1688api import Sync1688Session

with Sync1688Session(debug = False, proxies = proxies) as session:

    # 要修改会话参数，可以直接访问会话对象
    session.cookies_dict['_m_h5_tk'] = 'a5684f3729bb00ef0c8208249107d061_1720690129578'

    products = session.search_by_image("path/to/image.jpg")
    products = session.search_by_text("search query")
```

### 异步版本

```python
from search1688api import Async1688Session
import asyncio

proxy_url = "http://user:password@proxy.example.com:8080"

async def main():

    async with Async1688Session(debug = False, proxy = proxy_url) as session:
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
