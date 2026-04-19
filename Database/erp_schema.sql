-- 1. Create the Clients Table
CREATE TABLE Clients (
    NIF VARCHAR(20) PRIMARY KEY,
    Name VARCHAR(100) NOT NULL
);

-- 2. Create the Orders Table
CREATE TABLE Orders (
    OrderID VARCHAR(50) NOT NULL,
    Client_NIF VARCHAR(20) NOT NULL,
    DDate INT NOT NULL,
    Penalty_Per_Day DECIMAL(10, 2) NOT NULL,
    Total_Cost DECIMAL(10, 2) DEFAULT 0.00,
    Status VARCHAR(20) DEFAULT 'Pending',
    PRIMARY KEY (OrderID),
    FOREIGN KEY (Client_NIF) REFERENCES Clients(NIF)
);

-- 3. Create the Order Items Table
CREATE TABLE Order_Items (
    ItemID SERIAL PRIMARY KEY,
    OrderID VARCHAR(50) NOT NULL,
    Piece_Type VARCHAR(10) NOT NULL,
    Quantity_Ordered INT NOT NULL,
    Quantity_Done INT DEFAULT 0,
    FOREIGN KEY (OrderID) REFERENCES Orders(OrderID)
);

-- 4. Simulation Clock (seed=0 so first advance_day() correctly lands on Day 1)
CREATE TABLE Simulation_State (
    id INT PRIMARY KEY DEFAULT 1,
    current_day INT DEFAULT 0
);
INSERT INTO Simulation_State (id, current_day) VALUES (1, 0);

-- 5. MES Feedback — populated by MES when an order is completed.
-- MES must POST JSON to ERP port 6668:
-- { "OrderID": "101-RWM", "Pieces_Produced": 5, "Production_Cost": 125.50 }
CREATE TABLE Production_Feedback (
    ID SERIAL PRIMARY KEY,
    OrderID VARCHAR(50) NOT NULL,
    Pieces_Produced INT NOT NULL,
    Production_Cost DECIMAL(10, 2) NOT NULL,
    Received_At TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (OrderID) REFERENCES Orders(OrderID)
);
