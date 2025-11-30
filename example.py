from search1688api import Async1688Session
import asyncio
import json

async def main():
    
    # Using correct format
    async with Async1688Session() as session:
        response = await session.search_by_image("1.jpg")
        
        print(f"Products found: {len(response)}")
        
        if response:
            # Save first product to JSON file
            first_product = response[0]
            
            # Save to file with pretty formatting
            with open("first_product.json", "w", encoding="utf-8") as f:
                json.dump(first_product, f, ensure_ascii=False, indent=2)
            
            print("First product saved to file 'first_product.json'")
            
            # Display basic information about the first product
            print("\n=== BASIC INFORMATION ABOUT FIRST PRODUCT ===")
            product_data = first_product.get('data', {})
            print(f"ID: {product_data.get('offerId', 'Unknown')}")
            print(f"Title: {product_data.get('title', 'Unknown')}")
            print(f"Price: {product_data.get('priceInfo', {}).get('price', 'Unknown')}")
            print(f"Seller: {product_data.get('shopAddition', {}).get('text', 'Unknown')}")
            print(f"Location: {product_data.get('province', '')} {product_data.get('city', '')}")
            print(f"Sold: {product_data.get('saleQuantity', 0)} pcs")
            print(f"Orders: {product_data.get('bookedCount', 0)}")
            
            # Display tags
            tags = product_data.get('tags', [])
            if tags:
                tag_texts = [tag.get('text', '') for tag in tags if isinstance(tag, dict)]
                print(f"Tags: {', '.join(tag_texts)}")
            
        else:
            print("No products found")

asyncio.run(main())