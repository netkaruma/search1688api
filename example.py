import asyncio
from search1688api import Async1688Session, Sync1688Session

async def async_example():
    """Async example with search by image and detailed product parsing"""
    image_path = "test_image.jpg"
    
    async with Async1688Session() as session:
        # Search products by image
        products = await session.search_by_image(image_path)
        
        print(f"Found products: {len(products)}")
        
        # Display first 5 products
        for i, product in enumerate(products[:5], 1):
            print(f"PRODUCT #{i}")
            print(f"  Name: {product.name}")
            print(f"  Price: {product.price}")
            print(f"  Company: {product.company}")
            print(f"  URL: {product.url}")
            print("-" * 50)
        
        # Get detailed info for first product
        if products:
            first_product_id = products[0].id
            detailed_product = await session.get_by_id(first_product_id)
            
            if detailed_product:
                print("\nDETAILED PRODUCT INFO:")
                print(f"Brand: {detailed_product.brand}")
                print(f"Rating: {detailed_product.grade}")
                print(f"Sales: {detailed_product.saledCount}")
                print(f"Repeat orders: {detailed_product.repeat_orders}")
                
                print("\nPRODUCT VARIANTS:")
                for variant in detailed_product.goods:
                    print(f"  - {variant['name']}: {variant['price']}")
        
        return products

def sync_example():
    """Sync example with search by image and detailed product parsing"""
    image_path = "test_image.jpg"
    
    with Sync1688Session() as session:
        # Search products by image
        products = session.search_by_image(image_path)
        
        print(f"Found products: {len(products)}")
        
        # Display first 5 products
        for i, product in enumerate(products[:5], 1):
            print(f"PRODUCT #{i}")
            print(f"  Name: {product.name}")
            print(f"  Price: {product.price}")
            print(f"  Company: {product.company}")
            print(f"  URL: {product.url}")
            print("-" * 50)
        
        # Get detailed info for first product
        if products:
            first_product_id = products[0].id
            detailed_product = session.get_by_id(first_product_id)
            
            if detailed_product:
                print("\nDETAILED PRODUCT INFO:")
                print(f"Brand: {detailed_product.brand}")
                print(f"Rating: {detailed_product.grade}")
                print(f"Sales: {detailed_product.saledCount}")
                print(f"Repeat orders: {detailed_product.repeat_orders}")
                
                print("\nPRODUCT VARIANTS:")
                for variant in detailed_product.goods:
                    print(f"  - {variant['name']}: {variant['price']}")
        
        return products

def timeout_example():
    """Example with custom timeouts"""
    image_path = "test_image.jpg"
    
    with Sync1688Session(default_timeout=60) as session:
        # Search with custom timeout
        products = session.search_by_image(image_path, timeout=30)
        
        print(f"Found products: {len(products)}")
        
        if products:
            # Get detailed info with fast timeout
            detailed_product = session.get_by_id(products[0].id, timeout=15)
            
            if detailed_product:
                print(f"Detailed info for: {detailed_product.name}")
                print(f"Variants: {len(detailed_product.goods)}")
        
        return products

if __name__ == "__main__":
    print("=== SYNC EXAMPLE ===")
    sync_products = sync_example()
    
    print("\n=== ASYNC EXAMPLE ===")
    async_products = asyncio.run(async_example())
    
    print("\n=== TIMEOUT EXAMPLE ===")
    timeout_products = timeout_example()