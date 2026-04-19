-- 1. Track Production Orders from the ERP
CREATE TABLE Production_Orders (
    ID SERIAL PRIMARY KEY,
    OrderID VARCHAR(50) NOT NULL,
    Piece_Type VARCHAR(10) NOT NULL,
    Quantity_Ordered INT NOT NULL,
    Quantity_Produced INT DEFAULT 0,
    Status VARCHAR(20) DEFAULT 'Pending' -- Pending, In Progress, Completed
);

-- 2. Track Overall Machine Statistics
CREATE TABLE Machine_Stats (
    Machine_ID VARCHAR(10) PRIMARY KEY, -- e.g., 'M1a', 'M2c'
    Total_Operating_Sec INT DEFAULT 0,
    Tool_Changes INT DEFAULT 0,
    Pieces_Processed INT DEFAULT 0
);

-- 3. Track Tool-Specific Usage (Must track operating time per tool)
CREATE TABLE Tool_Stats (
    ID SERIAL PRIMARY KEY,
    Machine_ID VARCHAR(10) REFERENCES Machine_Stats(Machine_ID),
    Tool_ID VARCHAR(10) NOT NULL,
    Operating_Sec INT DEFAULT 0
);

-- 4. Track Unloaded Work-pieces
CREATE TABLE Unloading_Stats (
    ID SERIAL PRIMARY KEY,
    Dock_ID INT NOT NULL, -- 1 through 5
    Piece_Type VARCHAR(10) NOT NULL,
    Quantity_Unloaded INT DEFAULT 0
);