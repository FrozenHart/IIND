-- Shared database schema for ERP + MES (single PostgreSQL database).
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'iind_user') THEN
        EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', 'iind_user', 'IIND20266');
    ELSE
        EXECUTE format('ALTER ROLE %I WITH LOGIN PASSWORD %L', 'iind_user', 'IIND20266');
    END IF;
END
$$;

GRANT ALL PRIVILEGES ON DATABASE erp_db TO iind_user;

CREATE TABLE
    IF NOT EXISTS Clients (
        NIF VARCHAR(20) PRIMARY KEY,
        Name VARCHAR(100) NOT NULL
    );

CREATE TABLE
    IF NOT EXISTS Orders (
        OrderID VARCHAR(50) NOT NULL,
        Client_NIF VARCHAR(20) NOT NULL,
        DDate INT NOT NULL,
        Penalty_Per_Day DECIMAL(10, 2) NOT NULL,
        Total_Cost DECIMAL(10, 2) DEFAULT 0.00,
        Status VARCHAR(20) DEFAULT 'Pending',
        Estimated_Completion_Day INT DEFAULT NULL,
        PRIMARY KEY (OrderID),
        FOREIGN KEY (Client_NIF) REFERENCES Clients (NIF)
    );

CREATE TABLE
    IF NOT EXISTS Order_Items (
        ItemID SERIAL PRIMARY KEY,
        OrderID VARCHAR(50) NOT NULL,
        Piece_Type VARCHAR(10) NOT NULL,
        Quantity_Ordered INT NOT NULL,
        Quantity_Done INT DEFAULT 0,
        FOREIGN KEY (OrderID) REFERENCES Orders (OrderID)
    );

CREATE TABLE
    IF NOT EXISTS Simulation_State (
        id INT PRIMARY KEY DEFAULT 1,
        current_day INT DEFAULT 0
    );

INSERT INTO
    Simulation_State (id, current_day)
VALUES
    (1, 0) ON CONFLICT (id) DO NOTHING;

CREATE TABLE
    IF NOT EXISTS Production_Feedback (
        ID SERIAL PRIMARY KEY,
        OrderID VARCHAR(50) NOT NULL,
        Pieces_Produced INT NOT NULL,
        Production_Cost DECIMAL(10, 2) NOT NULL,
        Received_At TIMESTAMP DEFAULT NOW (),
        FOREIGN KEY (OrderID) REFERENCES Orders (OrderID)
    );

CREATE TABLE
    IF NOT EXISTS Production_Orders (
        ID SERIAL PRIMARY KEY,
        OrderID VARCHAR(50) NOT NULL,
        Piece_Type VARCHAR(10) NOT NULL,
        Quantity_Ordered INT NOT NULL,
        Production_Day INT DEFAULT 1,
        Quantity_Produced INT DEFAULT 0,
        Status VARCHAR(20) DEFAULT 'Pending'
    );

ALTER TABLE Orders ADD COLUMN IF NOT EXISTS Estimated_Completion_Day INT DEFAULT NULL;
ALTER TABLE Production_Orders DROP COLUMN IF EXISTS Estimated_Completion_Day;

CREATE TABLE
    IF NOT EXISTS Machine_Stats (
        Machine_ID VARCHAR(10) PRIMARY KEY,
        Total_Operating_Sec INT DEFAULT 0,
        Tool_Changes INT DEFAULT 0,
        Pieces_Processed INT DEFAULT 0
    );

CREATE TABLE
    IF NOT EXISTS Tool_Stats (
        ID SERIAL PRIMARY KEY,
        Machine_ID VARCHAR(10) REFERENCES Machine_Stats (Machine_ID),
        Tool_ID VARCHAR(10) NOT NULL,
        Operating_Sec INT DEFAULT 0
    );

CREATE TABLE
    IF NOT EXISTS Machine_Piece_Stats (
        ID SERIAL PRIMARY KEY,
        Machine_ID VARCHAR(10) REFERENCES Machine_Stats (Machine_ID),
        Piece_Type VARCHAR(10) NOT NULL,
        Pieces_Processed INT DEFAULT 0,
        UNIQUE (Machine_ID, Piece_Type)
    );

CREATE TABLE
    IF NOT EXISTS Unloading_Stats (
        ID SERIAL PRIMARY KEY,
        Dock_ID INT NOT NULL,
        Piece_Type VARCHAR(10) NOT NULL,
        Quantity_Unloaded INT DEFAULT 0
    );

CREATE TABLE
    IF NOT EXISTS Loading_Stats (
        ID SERIAL PRIMARY KEY,
        Conveyor_ID VARCHAR(10) NOT NULL,
        Piece_Type VARCHAR(10) NOT NULL,
        Quantity_Loaded INT DEFAULT 0,
        UNIQUE (Conveyor_ID, Piece_Type)
    );

CREATE INDEX IF NOT EXISTS idx_order_items_orderid ON Order_Items(OrderID);

GRANT USAGE, CREATE ON SCHEMA public TO iind_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO iind_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO iind_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO iind_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO iind_user;