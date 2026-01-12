0) Don't get me wrong, I understand compiling secure creds into a bin or pasting in a script is not a good answer unless your database is behind a firewall and is NOT serving active connections other than locally rather than living in a cloud. This python script and rust bin mains can at least serve as a testing grounds to evolve into something that could live in the cloud with live connections if needed, but these should only be used for development, or just for getting a full local dump of your shopify store for local usage only, and pushing changes to your shopify store, rather than as a live service in the cloud with active connections.

python script works fantastic as is and spells out the work flow with handlers, while rust bin code needs to be explicitly defined.

main.rs mirrors the python script, and tokio-postgres was a horrible option to experiment with at first, and ended up going with sqlx since tokio-postgres 0.8 isn't available natively yet in rust. I don't want to get into pulling github versions just to get this to work and would rather stick with native/stable.

--------------------------------------------------

The scripts/mains are based on the guidelines of

1) This is a working database, so if I make changes in the GUI, I can drop the database, recreate it, and re-import the data for complete clean import for further processing, such as additional tag, price, description changes, etc

2) errors/failure/etc in logging does not cause the script to exit, but will help offer additional data if shopify changes something, which might require you to reach out to the shopify chatbot for the new/updated canonical mirror CREATE TABLEs output which it is very helpful for providing, or at least at this time.

3) This is based on the older shpat keys, not the new keys and uses Shopify API from 10/2025.

4) The CREATE TABLES is created with the postgres superuser and the local users has access to manipulate the data only via the grants below

5) The following GRANTS  
GRANT CONNECT ON DATABASE shopify_db TO localusername; (this is what we actually did, so I don't break the schema)  
-- then connect to the DB (as superuser)  
\c shopify_db  
GRANT USAGE ON SCHEMA public TO localusername;  
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO localusername;  
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO localusername;-- needed for BIGSERIAL (tags, variant_shipping_costs)  

6) For the python script, be sure you put your info here instead of the placeholder strings I have
SHOPIFY_STORE = "shopify-store-name-url" #you don't have to put .shopify.com, just the store url name part'  
ACCESS_TOKEN = "shpat_SHORTSTRINGHERE"  
API_VERSION = "2025-10"  
PAGE_SIZE = 50  
BACKOFF = 2.0  

DB_HOST = "localhost"  
DB_NAME = "shopify_database"  
DB_USER = "databaseusernamegoeshere"  
DB_PASSWORD = "dbpasswordgoeshere"  

7) For the Rust mains, be sure you put your info here instead of the placeholders strings I have  
const SHOPIFY_STORE: &str = "store-uri";  
const ACCESS_TOKEN: &str = "shpat_SHORTSTRINGHERE";  
const API_VERSION: &str = "2025-10";  
const PAGE_SIZE: i64 = 50;  
const BACKOFF_SECS: u64 = 2;  

  const DB_HOST: &str = "localhostorip-locationofyourdatabase";  
  const DB_NAME: &str = "shopify-database-name-in-your-local-postgresql-18-node";  
  const DB_USER: &str = "localusernamethathandlesthedatagoeshere";  
  const DB_PASSWORD: &str = "databasepasswordgoeshere";  

8) the 2 second wait between calls is a friendly approach so your requests/account does not get dropped by Shopify admins. Dont pound their servers to death, you are not the only person that needs to use it.

9) chatgpt or your choice of ai bot should be able to help as long as you have not littered your logged in profile with random junk requests that only responds in encylopedia based rabbit hole responses. This is important for code development. If you build a garbage profile with your current login, you will only get garbage as a response in most cases, with rabbit holes that are possibly filled with positive hallucination feedback loops, optimism bias, pessimism bias, and straight out inventing things that don't exist, so be sure when you make you're requests for correcting code, that you tell the chatbot to NOT optimize outside of scope, don't break my code, and don't invent things that don't exist for the sake of creative programming.

10) this was built and tested in Ubuntu 24.04 LTS. If you have problems with your postgresql having issues on boot, you may need to restart your postgresql service, as in debian based architectures it has a tendency to lock onto the port before the network service comes up. I just set a cron job to restart the service after the server has been up for 10 seconds, as this is the least invasive way to fix this on boot.

11) I'm using the official rust install and running rustup update. I am NOT using the apt or snap based installations.


