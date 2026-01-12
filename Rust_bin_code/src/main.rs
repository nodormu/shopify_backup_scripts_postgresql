use anyhow::{Context, Result};
use reqwest::Client;
use serde_json::json;
use tokio::time::{sleep, Duration};
use sqlx::postgres::PgPoolOptions;
use chrono::{DateTime, Utc};
use sqlx::types::BigDecimal;
use std::str::FromStr;

const SHOPIFY_STORE: &str = "um7n0e-i5";
const ACCESS_TOKEN: &str = "shpat_SHORTSTRINGHERE";
const API_VERSION: &str = "2025-10";
const PAGE_SIZE: i64 = 50;
const BACKOFF_SECS: u64 = 2;

const DB_HOST: &str = "localhost";
const DB_NAME: &str = "shopify_db";
const DB_USER: &str = "dbusername";
const DB_PASSWORD: &str = "dbpassword";

const GRAPHQL_QUERY: &str = r#"
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
"#;

#[tokio::main]
async fn main() -> Result<()> {
    fetch_and_insert().await
}

async fn fetch_and_insert() -> Result<()> {
    let graphql_endpoint = format!(
        "https://{}.myshopify.com/admin/api/{}/graphql.json",
        SHOPIFY_STORE, API_VERSION
    );

    let client = Client::new();

    // sqlx connection string format
    let db_url = format!(
        "postgres://{}:{}@{}/{}",
        DB_USER, DB_PASSWORD, DB_HOST, DB_NAME
    );

    // Create connection pool
    let pool = PgPoolOptions::new()
        .max_connections(5)
        .connect(&db_url)
        .await?;

    let mut cursor: Option<String> = None;
    let mut total_pages = 0;

    loop {
        let payload = json!({
            "query": GRAPHQL_QUERY,
            "variables": { "first": PAGE_SIZE, "after": cursor }
        });

        let resp = client
            .post(&graphql_endpoint)
            .header("X-Shopify-Access-Token", ACCESS_TOKEN)
            .json(&payload)
            .send()
            .await?
            .error_for_status()?;

        let data: serde_json::Value = resp.json().await?;

        let products: &[serde_json::Value] = data["data"]["products"]["edges"]
            .as_array()
            .map(|v| v.as_slice())
            .unwrap_or(&[]);

        if products.is_empty() {
            break;
        }

        for product in products {
            let node = &product["node"];
            let product_id = node["id"].as_str().unwrap_or_default().to_string();
            let title = node["title"].as_str().map(String::from);
            let handle = node["handle"].as_str().map(String::from);
            let product_type = node["productType"].as_str().map(String::from);
            let vendor = node["vendor"].as_str().map(String::from);
            let online_store_url = node["onlineStoreUrl"].as_str().map(String::from);
            let description = node["description"].as_str().map(String::from);
            let description_html = node["descriptionHtml"].as_str().map(String::from);

            // Parse timestamp properly with chrono
            let published_at: Option<DateTime<Utc>> = node["publishedAt"]
                .as_str()
                .and_then(|s| DateTime::parse_from_rfc3339(s).ok())
                .map(|dt| dt.with_timezone(&Utc));

            // Convert tags to Vec<String> - sqlx handles arrays natively
            let tags: Option<Vec<String>> = node["tags"]
                .as_array()
                .map(|arr| {
                    arr.iter()
                        .filter_map(|v| v.as_str().map(String::from))
                        .collect()
                });

            if let Err(e) = sqlx::query(
                r#"
                INSERT INTO products (
                    id, title, handle, product_type, vendor, tags,
                    published_at, online_store_url, description, description_html
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                ON CONFLICT (id) DO UPDATE SET
                    title = EXCLUDED.title,
                    handle = EXCLUDED.handle,
                    product_type = EXCLUDED.product_type,
                    vendor = EXCLUDED.vendor,
                    tags = EXCLUDED.tags,
                    published_at = EXCLUDED.published_at,
                    online_store_url = EXCLUDED.online_store_url,
                    description = EXCLUDED.description,
                    description_html = EXCLUDED.description_html
                "#,
            )
            .bind(&product_id)
            .bind(&title)
            .bind(&handle)
            .bind(&product_type)
            .bind(&vendor)
            .bind(&tags)
            .bind(&published_at)
            .bind(&online_store_url)
            .bind(&description)
            .bind(&description_html)
            .execute(&pool)
            .await
            .with_context(|| format!("products insert failed ({})", product_id)) {
                eprintln!("{:#}", e);
            }

            let variants: &[serde_json::Value] = node["variants"]["edges"]
                .as_array()
                .map(|v| v.as_slice())
                .unwrap_or(&[]);

            for v in variants {
                let vn = &v["node"];
                let variant_id = vn["id"].as_str().unwrap_or_default().to_string();
                let sku = vn["sku"].as_str().map(String::from);
                let barcode = vn["barcode"].as_str().map(String::from);

                // Parse strings to BigDecimal for numeric columns
                let price: Option<BigDecimal> = vn["price"]
                    .as_str()
                    .and_then(|s| BigDecimal::from_str(s).ok());

                let compare_at_price: Option<BigDecimal> = vn["compareAtPrice"]
                    .as_str()
                    .and_then(|s| BigDecimal::from_str(s).ok());

                let inventory_quantity = vn["inventoryQuantity"].as_i64().map(|v| v as i32);
                let available_for_sale = vn["availableForSale"].as_bool();

                // ... rest of your code stays the same


                let inv = &vn["inventoryItem"];
                let (weight, weight_unit, inventory_item_id) = if inv.is_object() {
                    (
                    // Parse weight to BigDecimal instead of String
                        inv["measurement"]["weight"]["value"]
                            .as_str()
                            .and_then(|s| BigDecimal::from_str(s).ok()),
                        inv["measurement"]["weight"]["unit"].as_str().map(String::from),
                        inv["id"].as_str().map(String::from),
                    )
                } else {
                    (None, None, None)
                };

                if let Err(e) = sqlx::query(
                    r#"
                    INSERT INTO product_variants (
                        id, product_id, sku, price, compare_at_price,
                        inventory_quantity, barcode, available_for_sale,
                        weight, weight_unit, inventory_item_id
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                    ON CONFLICT (id) DO UPDATE SET
                        sku = EXCLUDED.sku,
                        price = EXCLUDED.price,
                        compare_at_price = EXCLUDED.compare_at_price,
                        inventory_quantity = EXCLUDED.inventory_quantity,
                        barcode = EXCLUDED.barcode,
                        available_for_sale = EXCLUDED.available_for_sale,
                        weight = EXCLUDED.weight,
                        weight_unit = EXCLUDED.weight_unit,
                        inventory_item_id = EXCLUDED.inventory_item_id
                    "#,
                )
                .bind(&variant_id)
                .bind(&product_id)
                .bind(&sku)
                .bind(&price)
                .bind(&compare_at_price)
                .bind(&inventory_quantity)
                .bind(&barcode)
                .bind(&available_for_sale)
                .bind(&weight)
                .bind(&weight_unit)
                .bind(&inventory_item_id)
                .execute(&pool)
                .await
                .with_context(|| format!("variant insert failed ({})", variant_id)) {
                    eprintln!("{:#}", e);
                }
            }
        }

        total_pages += 1;
        println!("Processed {} product pages so far...", total_pages);

        let page_info = &data["data"]["products"]["pageInfo"];
        if page_info["hasNextPage"].as_bool().unwrap_or(false) {
            cursor = Some(page_info["endCursor"].as_str().unwrap_or_default().to_string());
            sleep(Duration::from_secs(BACKOFF_SECS)).await;
        } else {
            break;
        }
    }

    println!("Import complete. Total pages processed: {}", total_pages);
    Ok(())
}
