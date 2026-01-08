# shopify_backup_scripts_postgresql
This repo has the canonical CREATE TABLES for Postgresql 18 and a python script which may be migrated to Rust soon for backing up your shopify storefront.
This was done on Ubuntu 24.04 LTS with Postgres official repo/installation of postgresql 18.
Python script was built using Python 3.12.x
Be sure you check the variables and change them for your environment:  username, db password, db name.
This particular script uses the shpat_SHORTSTRINGAPIKEY format vs the newer format they are moving to soon.
This uses Graph QL mutations as it works better than Shopify's deprecated REST API.
You need the following python packages:  requests, psycopg2 and time 
psycopg2 requires some additional global packages installed along with the python package, a simple query to chatgpt should give you the dependencies you need to install
Here is what I setup on my Ubuntu 24.04 LTS dev box.


sudo apt update

sudo apt install -y \
    python3-dev \
    libpq-dev \
    build-essential \
    gcc \
    libssl-dev \
    libffi-dev \
    python3-venv \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev
