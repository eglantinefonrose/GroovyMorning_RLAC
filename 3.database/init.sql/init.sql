CREATE TABLE IF NOT EXISTS chronicle_events (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    chronicle_name VARCHAR(255) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    timestamp VARCHAR(255),
    delta DOUBLE PRECISION,
    duration VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
