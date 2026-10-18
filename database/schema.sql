-- Datenbank-Schema für PropMAgent

CREATE TABLE IF NOT EXISTS properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    street TEXT NOT NULL,
    zip_code TEXT NOT NULL,
    city TEXT NOT NULL,
    total_area_sqm REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL,
    unit_number TEXT NOT NULL,
    floor TEXT,
    area_sqm REAL NOT NULL,
    FOREIGN KEY (property_id) REFERENCES properties (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tenants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    lease_start DATE NOT NULL,
    lease_end DATE,
    cold_rent REAL NOT NULL,
    utility_advance REAL NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    FOREIGN KEY (unit_id) REFERENCES units (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL,
    year INTEGER NOT NULL,
    category TEXT NOT NULL,
    description TEXT,
    amount REAL NOT NULL,
    allocation_key TEXT DEFAULT 'sqm', -- 'sqm' (Quadratmeter), 'units' (Wohneinheiten), 'direct'
    receipt_date DATE,
    FOREIGN KEY (property_id) REFERENCES properties (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    payment_date DATE NOT NULL,
    amount REAL NOT NULL,
    payment_type TEXT DEFAULT 'total', -- 'cold_rent', 'utility_advance', 'total'
    FOREIGN KEY (tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);
