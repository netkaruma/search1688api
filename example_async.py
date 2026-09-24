import asyncio
from search1688api import Async1688Session

PROXY_URL = "http://user:password@proxy.example.com:8080"


async def main():
    async with Async1688Session(debug=True, proxy=PROXY_URL) as session:
        session.cookies_dict['_m_h5_tk'] = 'a5684f3729bb00ef0c8208249107d061_1720690129578'
        session.cookies_dict['my_custom_cookie'] = 'my_custom_value'
        session.cookies_dict['auth_token'] = 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'

        products_img = await session.search_by_image("path/to/image.jpg")
        print(f"Products found based on the image: {len(products_img)}")

        products_txt = await session.search_by_text("wireless earbuds")
        print(f"Products found based on the text: {len(products_txt)}")


if __name__ == "__main__":
    asyncio.run(main())