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

sudo apt install -y python3-dev libpq-dev build-essential gcc libssl-dev libffi-dev python3-venv libxml2-dev libxslt1-dev zlib1g-dev python3-pip

If you have a barebones install, you are going to see a TON of more related deps get installed. This is expected.

Then create your python venv sandbox, activate your python sandbox and install this:  pip install psycopg2-binary requests time psycopg2

After you get postgresql installed and the database created, here are the GRANTs for your user you will need.
Consider using the postgres superuser to create the database and the tables, then specify a user for handling the data on the database so the schema does not get jacked up/broken/etc.

here are the GRANTS I used on my dev box for the local user

I establish this while in the postgres default db, don't forget the ; at the end.

GRANT CONNECT ON DATABASE shopify_db TO localusername;

then change to the shopify db (no ; required here because its built in command \c)

\c shopify_db

and set these GRANTS. Be sure you have your ; in place.

GRANT USAGE ON SCHEMA public TO localusername;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO localusername;

GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO localusername;

\quit
