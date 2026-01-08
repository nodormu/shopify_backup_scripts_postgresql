# shopify_backup_scripts_postgresql
This repo has the canonical CREATE TABLES for Postgresql 18 and a python script which may be migrated to Rust soon for backing up your shopify storefront.
This was done on Ubuntu 24.04 LTS with Postgres official repo/installation of postgresql 18.
Python script was built using Python 3.12.x
Be sure you check the variables and change them for your environment:  username, db password, db name.
This particular script uses the shpat_SHORTSTRINGAPIKEY format vs the newer format they are moving to soon.
This uses Graph QL mutations as it works better than Shopify's deprecated REST API.
