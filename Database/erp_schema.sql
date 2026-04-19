-- 1. Create the Clients Table
CREATE TABLE Clients (
    NIF VARCHAR(20) PRIMARY KEY,
    Name VARCHAR(100) NOT NULL
);

-- 2. Create the Orders Table
CREATE TABLE Orders (
    OrderID VARCHAR(50) PRIMARY KEY,
    Client_NIF VARCHAR(20) NOT NULL,
    Delivery_Date INT NOT NULL, 
    Penalty_Per_Sec DECIMAL(10, 2) NOT NULL,
    Max_Penalty DECIMAL(10, 2) NOT NULL,
    Total_Cost DECIMAL(10, 2) DEFAULT 0.00,
    Status VARCHAR(20) DEFAULT 'Pending', 
    FOREIGN KEY (Client_NIF) REFERENCES Clients(NIF)
);

-- 3. Create the Order Items Table
CREATE TABLE Order_Items (
    ItemID SERIAL PRIMARY KEY, -- This is the PostgreSQL version of Auto_Increment
    OrderID VARCHAR(50) NOT NULL,
    Piece_Type VARCHAR(10) NOT NULL, 
    Quantity_Ordered INT NOT NULL,
    Quantity_Done INT DEFAULT 0,
    FOREIGN KEY (OrderID) REFERENCES Orders(OrderID)