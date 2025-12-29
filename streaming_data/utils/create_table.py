import logging
from utils.postgresql_client import PostgresSQLClient

# Define the schema matching product data schema
CREATE_PRODUCTS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS products (
        id VARCHAR(50) PRIMARY KEY,
        gender VARCHAR(50),
        masterCategory VARCHAR(100),
        subCategory VARCHAR(100),
        articleType VARCHAR(100),
        baseColour VARCHAR(50),
        season VARCHAR(50),
        year INT,
        usage VARCHAR(50),
        productDisplayName TEXT,
        image_embedding FLOAT[],  -- Store vector as array of floats
        text_embedding FLOAT[],   -- Store vector as array of floats
        image_url TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
"""

def create_tables():
    db_client = PostgresSQLClient(
        database="k6",
        user="k6",
        password="k6",
    )
    try:
        with db_client.create_conn() as conn:
            with conn.cursor() as cur:
                logging.info("Creating table 'products' if not exists...")
                cur.execute(CREATE_PRODUCTS_TABLE_SQL)
            conn.commit()
        logging.info("Database schema initialized successfully.")
    except Exception as e:
        logging.error(f"Error creating tables: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    create_tables()