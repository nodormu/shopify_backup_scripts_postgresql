#!/usr/bin/env python3
# import_shopify_data_to_postgres_extended_v12.py
# Programmer's notes:
# - Full product + variant import from Shopify to local PostgreSQL.
# - Preserves images, options, variant images, selected options, pagination, batching, backoff.
# - Adds inventory_item_id, weight, weight_unit, and ensures all variant fields needed for barcode updates are populated.
# - Does not remove any existing functionality from V11.

import requests
import psycopg2
import time

# =========================
# CONFIG VARIABLES
# =========================
SHOPIFY_STORE = "shopify-store-name-url" #you don't have to put .shopify.com, just the store url name part'
ACCESS_TOKEN = "shpat_SHORTSTRINGHERE"
API_VERSION = "2025-10"
PAGE_SIZE = 50
BACKOFF = 2.0

DB_HOST = "localhost"
DB_NAME = "shopify_database"
DB_USER = "databaseusernamegoeshere"
DB_PASSWORD = "dbpasswordgoeshere"

GRAPHQL_ENDPOINT = f"https://{SHOPIFY_STORE}.myshopify.com/admin/api/{API_VERSION}/graphql.json"
HEADERS = {
    "Content-Type": "application/json",
    "X-Shopify-Access-Token": ACCESS_TOKEN
}

# =========================
# GRAPHQL QUERY
# =========================
QUERY = """
query getProducts($first: Int!, $after: String) {
  products(first: $first, after: $after) {
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        id
        title
        handle
        productType
        vendor
        tags
        publishedAt
        onlineStoreUrl
        description
        descriptionHtml
        images(first: 10) { edges { node { id src altText } } }
        options { name position values }
        variants(first: 50) {
          edges {
            node {
              id
              sku
              price
              compareAtPrice
              inventoryQuantity
              barcode
              availableForSale
              selectedOptions { name value }
              image { id src }

              # ===== FETCH INVENTORY ITEM + WEIGHT =====
              inventoryItem {
                id
                measurement {
                  weight {
                    value
                    unit
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
"""

# =========================
# FETCH & INSERT FUNCTION
# =========================
def fetch_and_insert():
    cursor_val = None
    total_inserted = 0

    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()

    while True:
        payload = {"query": QUERY, "variables": {"first": PAGE_SIZE, "after": cursor_val}}
        resp = requests.post(GRAPHQL_ENDPOINT, json=payload, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if "errors" in data:
            raise Exception(f"GraphQL errors: {data['errors']}")

        products = data.get("data", {}).get("products", {}).get("edges", [])
        if not products:
            print("No products returned on this page.")
            break

        for p in products:
            node = p.get("node", {})
            product_id = node.get("id")
            title = node.get("title")
            handle = node.get("handle")
            online_store_url = node.get("onlineStoreUrl")
            product_type = node.get("productType")
            vendor = node.get("vendor")
            tags = node.get("tags", [])
            published_at = node.get("publishedAt")
            description = node.get("description")
            description_html = node.get("descriptionHtml")

            tags_array = (
                "{" + ",".join(tag.replace('"', '\\"').replace("'", "''") for tag in tags) + "}"
                if tags else None
            )

            # =========================
            # PRODUCTS TABLE
            # =========================
            cur.execute("""
                INSERT INTO products (id, title, handle, product_type, vendor, tags, published_at, online_store_url, description, description_html)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE
                SET title = EXCLUDED.title,
                    handle = EXCLUDED.handle,
                    product_type = EXCLUDED.product_type,
                    vendor = EXCLUDED.vendor,
                    tags = EXCLUDED.tags,
                    published_at = EXCLUDED.published_at,
                    online_store_url = EXCLUDED.online_store_url,
                    description = EXCLUDED.description,
                    description_html = EXCLUDED.description_html;
            """, (product_id, title, handle, product_type, vendor, tags_array, published_at, online_store_url, description, description_html))

            # =========================
            # PRODUCT IMAGES
            # =========================
            images = node.get("images", {}).get("edges", [])
            for img in images:
                img_node = img.get("node", {})
                image_id = img_node.get("id")
                url = img_node.get("url") or img_node.get("src")
                alt_text = img_node.get("altText")

                if image_id and url:
                    cur.execute("""
                        INSERT INTO product_images (id, product_id, url, alt_text)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (id) DO NOTHING;
                    """, (image_id, product_id, url, alt_text))

            # =========================
            # PRODUCT OPTIONS
            # =========================
            options = node.get("options", [])
            for opt in options:
                name = opt.get("name")
                position = opt.get("position")
                values = opt.get("values", [])
                values_array = "{" + ",".join(v.replace('"', '\\"').replace("'", "''") for v in values if v) + "}" if values else None

                if name:
                    cur.execute("""
                        INSERT INTO product_options (product_id, name, position, values)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT DO NOTHING;
                    """, (product_id, name, position, values_array))

            # =========================
            # PRODUCT VARIANTS
            # =========================
            variants = node.get("variants", {}).get("edges", [])
            for v in variants:
                var_node = v.get("node", {})
                variant_id = var_node.get("id")
                sku = var_node.get("sku")
                price = var_node.get("price")
                compare_at_price = var_node.get("compareAtPrice")
                inventory_qty = var_node.get("inventoryQuantity")
                barcode = var_node.get("barcode")
                available_for_sale = var_node.get("availableForSale")

                # ===== FETCH INVENTORY ITEM + WEIGHT =====
                inv_item = var_node.get("inventoryItem")
                if inv_item:
                    inventory_item_id = inv_item.get("id")
                    if inv_item.get("measurement") and inv_item["measurement"].get("weight"):
                        weight_value = inv_item["measurement"]["weight"].get("value")
                        weight_unit = inv_item["measurement"]["weight"].get("unit")
                    else:
                        weight_value = None
                        weight_unit = None
                else:
                    inventory_item_id = None
                    weight_value = None
                    weight_unit = None

                cur.execute("""
                    INSERT INTO product_variants (
                        id, product_id, sku, price, compare_at_price, inventory_quantity, barcode, available_for_sale, weight, weight_unit, inventory_item_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE
                    SET sku = EXCLUDED.sku,
                        price = EXCLUDED.price,
                        compare_at_price = EXCLUDED.compare_at_price,
                        inventory_quantity = EXCLUDED.inventory_quantity,
                        barcode = EXCLUDED.barcode,
                        available_for_sale = EXCLUDED.available_for_sale,
                        weight = EXCLUDED.weight,
                        weight_unit = EXCLUDED.weight_unit,
                        inventory_item_id = EXCLUDED.inventory_item_id;
                """, (variant_id, product_id, sku, price, compare_at_price, inventory_qty, barcode, available_for_sale, weight_value, weight_unit, inventory_item_id))

                # =========================
                # VARIANT SELECTED OPTIONS
                # =========================
                selected_options = var_node.get("selectedOptions", [])
                for so in selected_options:
                    opt_name = so.get("name")
                    opt_value = so.get("value")
                    if opt_name and opt_value:
                        cur.execute("""
                            INSERT INTO variant_selected_options (variant_id, option_name, option_value)
                            VALUES (%s, %s, %s)
                            ON CONFLICT DO NOTHING;
                        """, (variant_id, opt_name, opt_value))

                # =========================
                # VARIANT IMAGE LINK (safe)
                # =========================
                variant_image = var_node.get("image")
                if variant_image:
                    image_id = variant_image.get("id")
                    if image_id:
                        cur.execute("""
                            INSERT INTO variant_images (variant_id, image_id)
                            SELECT %s, %s
                            WHERE EXISTS (SELECT 1 FROM product_images WHERE id = %s)
                            ON CONFLICT DO NOTHING;
                        """, (variant_id, image_id, image_id))

        conn.commit()
        total_inserted += len(products)
        print(f"Processed {total_inserted} product pages so far...")

        page_info = data.get("data", {}).get("products", {}).get("pageInfo", {})
        if page_info.get("hasNextPage"):
            cursor_val = page_info.get("endCursor")
            time.sleep(BACKOFF)
        else:
            break

    cur.close()
    conn.close()
    print(f"Import complete. Total product pages processed: {total_inserted}")

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    fetch_and_insert()
