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

-- 3. Simulation Clock (1 row, current_day increments each dispatch cycle)
CREATE TABLE Simulation_State (
    id INT PRIMARY KEY DEFAULT 1,
    current_day INT DEFAULT 1
);
INSERT INTO Simulation_State (id, current_day) VALUES (1, 1);

-- 4. Create the Order Items Table
CREATE TABLE Order_Items (
    ItemID SERIAL PRIMARY KEY,
    OrderID VARCHAR(50) NOT NULL,
    Piece_Type VARCHAR(10) NOT NULL,
    Quantity_Ordered INT NOT NULL,
    Quantity_Done INT DEFAULT 0,
    FOREIGN KEY (OrderID) REFERENCES Orders(OrderID)
);
