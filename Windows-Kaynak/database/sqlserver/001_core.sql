SET XACT_ABORT ON;
GO

CREATE TABLE dbo.organizations (
    id bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    code nvarchar(30) NOT NULL UNIQUE,
    name nvarchar(200) NOT NULL,
    active bit NOT NULL CONSTRAINT DF_organizations_active DEFAULT 1,
    created_at datetime2(0) NOT NULL CONSTRAINT DF_organizations_created DEFAULT SYSUTCDATETIME(),
    row_version rowversion NOT NULL
);
GO

CREATE TABLE dbo.roles (
    id bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    organization_id bigint NOT NULL,
    code nvarchar(40) NOT NULL,
    name nvarchar(100) NOT NULL,
    permissions_json nvarchar(max) NOT NULL CONSTRAINT DF_roles_permissions DEFAULT N'[]',
    active bit NOT NULL CONSTRAINT DF_roles_active DEFAULT 1,
    CONSTRAINT FK_roles_organization FOREIGN KEY (organization_id) REFERENCES dbo.organizations(id),
    CONSTRAINT UQ_roles_code UNIQUE (organization_id, code)
);
GO

CREATE TABLE dbo.app_users (
    id bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    organization_id bigint NOT NULL,
    role_id bigint NOT NULL,
    username nvarchar(80) NOT NULL,
    display_name nvarchar(160) NOT NULL,
    password_salt varbinary(64) NOT NULL,
    password_hash varbinary(64) NOT NULL,
    active bit NOT NULL CONSTRAINT DF_app_users_active DEFAULT 1,
    failed_login_count int NOT NULL CONSTRAINT DF_app_users_failed DEFAULT 0,
    locked_until datetime2(0) NULL,
    created_at datetime2(0) NOT NULL CONSTRAINT DF_app_users_created DEFAULT SYSUTCDATETIME(),
    updated_at datetime2(0) NOT NULL CONSTRAINT DF_app_users_updated DEFAULT SYSUTCDATETIME(),
    row_version rowversion NOT NULL,
    CONSTRAINT FK_app_users_organization FOREIGN KEY (organization_id) REFERENCES dbo.organizations(id),
    CONSTRAINT FK_app_users_role FOREIGN KEY (role_id) REFERENCES dbo.roles(id),
    CONSTRAINT UQ_app_users_username UNIQUE (organization_id, username)
);
GO

CREATE TABLE dbo.customers (
    id bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    organization_id bigint NOT NULL,
    code nvarchar(50) NOT NULL,
    name nvarchar(250) NOT NULL,
    tax_office nvarchar(100) NULL,
    tax_number nvarchar(40) NULL,
    phone nvarchar(60) NULL,
    email nvarchar(180) NULL,
    address nvarchar(600) NULL,
    city nvarchar(100) NULL,
    country nvarchar(100) NULL,
    sales_representative nvarchar(160) NULL,
    currency char(3) NOT NULL CONSTRAINT DF_customers_currency DEFAULT 'TRY',
    active bit NOT NULL CONSTRAINT DF_customers_active DEFAULT 1,
    created_at datetime2(0) NOT NULL CONSTRAINT DF_customers_created DEFAULT SYSUTCDATETIME(),
    updated_at datetime2(0) NOT NULL CONSTRAINT DF_customers_updated DEFAULT SYSUTCDATETIME(),
    row_version rowversion NOT NULL,
    CONSTRAINT FK_customers_organization FOREIGN KEY (organization_id) REFERENCES dbo.organizations(id),
    CONSTRAINT UQ_customers_code UNIQUE (organization_id, code)
);
GO

CREATE TABLE dbo.suppliers (
    id bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    organization_id bigint NOT NULL,
    code nvarchar(50) NOT NULL,
    name nvarchar(250) NOT NULL,
    supplier_type nvarchar(50) NOT NULL CONSTRAINT DF_suppliers_type DEFAULT N'TEDARİKÇİ',
    phone nvarchar(60) NULL,
    email nvarchar(180) NULL,
    address nvarchar(600) NULL,
    active bit NOT NULL CONSTRAINT DF_suppliers_active DEFAULT 1,
    row_version rowversion NOT NULL,
    CONSTRAINT FK_suppliers_organization FOREIGN KEY (organization_id) REFERENCES dbo.organizations(id),
    CONSTRAINT UQ_suppliers_code UNIQUE (organization_id, code)
);
GO

CREATE TABLE dbo.profiles (
    id bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    organization_id bigint NOT NULL,
    customer_id bigint NULL,
    profile_code nvarchar(60) NOT NULL,
    profile_name nvarchar(250) NOT NULL,
    profile_group nvarchar(100) NULL,
    unit_weight_kg_m decimal(18,6) NOT NULL CONSTRAINT DF_profiles_weight DEFAULT 0,
    perimeter_mm decimal(18,4) NOT NULL CONSTRAINT DF_profiles_perimeter DEFAULT 0,
    area_mm2 decimal(18,4) NOT NULL CONSTRAINT DF_profiles_area DEFAULT 0,
    alloy nvarchar(30) NOT NULL CONSTRAINT DF_profiles_alloy DEFAULT N'6060B',
    temper nvarchar(30) NOT NULL CONSTRAINT DF_profiles_temper DEFAULT N'T5',
    active bit NOT NULL CONSTRAINT DF_profiles_active DEFAULT 1,
    created_at datetime2(0) NOT NULL CONSTRAINT DF_profiles_created DEFAULT SYSUTCDATETIME(),
    updated_at datetime2(0) NOT NULL CONSTRAINT DF_profiles_updated DEFAULT SYSUTCDATETIME(),
    row_version rowversion NOT NULL,
    CONSTRAINT FK_profiles_organization FOREIGN KEY (organization_id) REFERENCES dbo.organizations(id),
    CONSTRAINT FK_profiles_customer FOREIGN KEY (customer_id) REFERENCES dbo.customers(id),
    CONSTRAINT UQ_profiles_code UNIQUE (organization_id, profile_code)
);
GO

CREATE TABLE dbo.dies (
    id bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    organization_id bigint NOT NULL,
    profile_id bigint NOT NULL,
    supplier_id bigint NULL,
    die_code nvarchar(80) NOT NULL,
    spare_no int NOT NULL CONSTRAINT DF_dies_spare DEFAULT 0,
    figure_count int NOT NULL CONSTRAINT DF_dies_figure DEFAULT 1,
    diameter_mm decimal(18,2) NOT NULL CONSTRAINT DF_dies_diameter DEFAULT 0,
    life_limit_kg decimal(18,3) NOT NULL CONSTRAINT DF_dies_life DEFAULT 0,
    used_kg decimal(18,3) NOT NULL CONSTRAINT DF_dies_used DEFAULT 0,
    tenefer_limit_m decimal(18,3) NOT NULL CONSTRAINT DF_dies_tenefer_limit DEFAULT 0,
    tenefer_used_m decimal(18,3) NOT NULL CONSTRAINT DF_dies_tenefer_used DEFAULT 0,
    status nvarchar(40) NOT NULL CONSTRAINT DF_dies_status DEFAULT N'AKTİF',
    location nvarchar(100) NULL,
    note nvarchar(max) NULL,
    row_version rowversion NOT NULL,
    CONSTRAINT FK_dies_organization FOREIGN KEY (organization_id) REFERENCES dbo.organizations(id),
    CONSTRAINT FK_dies_profile FOREIGN KEY (profile_id) REFERENCES dbo.profiles(id),
    CONSTRAINT FK_dies_supplier FOREIGN KEY (supplier_id) REFERENCES dbo.suppliers(id),
    CONSTRAINT UQ_dies_code UNIQUE (organization_id, die_code, spare_no)
);
GO

CREATE TABLE dbo.warehouses (
    id bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    organization_id bigint NOT NULL,
    code nvarchar(40) NOT NULL,
    name nvarchar(120) NOT NULL,
    warehouse_type nvarchar(40) NOT NULL,
    active bit NOT NULL CONSTRAINT DF_warehouses_active DEFAULT 1,
    CONSTRAINT FK_warehouses_organization FOREIGN KEY (organization_id) REFERENCES dbo.organizations(id),
    CONSTRAINT UQ_warehouses_code UNIQUE (organization_id, code)
);
GO

CREATE TABLE dbo.stock_items (
    id bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    organization_id bigint NOT NULL,
    profile_id bigint NULL,
    code nvarchar(80) NOT NULL,
    name nvarchar(250) NOT NULL,
    stock_group nvarchar(80) NOT NULL,
    unit nvarchar(20) NOT NULL,
    tracks_lot bit NOT NULL CONSTRAINT DF_stock_items_lot DEFAULT 0,
    minimum_quantity decimal(18,4) NOT NULL CONSTRAINT DF_stock_items_min DEFAULT 0,
    active bit NOT NULL CONSTRAINT DF_stock_items_active DEFAULT 1,
    row_version rowversion NOT NULL,
    CONSTRAINT FK_stock_items_organization FOREIGN KEY (organization_id) REFERENCES dbo.organizations(id),
    CONSTRAINT FK_stock_items_profile FOREIGN KEY (profile_id) REFERENCES dbo.profiles(id),
    CONSTRAINT UQ_stock_items_code UNIQUE (organization_id, code)
);
GO

CREATE TABLE dbo.sales_orders (
    id bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    organization_id bigint NOT NULL,
    customer_id bigint NOT NULL,
    order_no nvarchar(60) NOT NULL,
    revision_no int NOT NULL CONSTRAINT DF_sales_orders_revision DEFAULT 0,
    customer_document_no nvarchar(100) NULL,
    msp nvarchar(100) NULL,
    order_date date NOT NULL,
    delivery_date date NOT NULL,
    currency char(3) NOT NULL CONSTRAINT DF_sales_orders_currency DEFAULT 'TRY',
    status nvarchar(40) NOT NULL CONSTRAINT DF_sales_orders_status DEFAULT N'ONAY BEKLİYOR',
    production_approval nvarchar(30) NOT NULL CONSTRAINT DF_sales_orders_prod_approval DEFAULT N'BEKLİYOR',
    representative nvarchar(160) NULL,
    note nvarchar(max) NULL,
    created_by bigint NOT NULL,
    created_at datetime2(0) NOT NULL CONSTRAINT DF_sales_orders_created DEFAULT SYSUTCDATETIME(),
    updated_at datetime2(0) NOT NULL CONSTRAINT DF_sales_orders_updated DEFAULT SYSUTCDATETIME(),
    row_version rowversion NOT NULL,
    CONSTRAINT FK_sales_orders_organization FOREIGN KEY (organization_id) REFERENCES dbo.organizations(id),
    CONSTRAINT FK_sales_orders_customer FOREIGN KEY (customer_id) REFERENCES dbo.customers(id),
    CONSTRAINT FK_sales_orders_user FOREIGN KEY (created_by) REFERENCES dbo.app_users(id),
    CONSTRAINT UQ_sales_orders_no UNIQUE (organization_id, order_no, revision_no)
);
GO

CREATE TABLE dbo.sales_order_lines (
    id bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    sales_order_id bigint NOT NULL,
    line_no int NOT NULL,
    profile_id bigint NOT NULL,
    die_id bigint NULL,
    stock_length_mm int NOT NULL,
    production_length_mm int NOT NULL,
    surface nvarchar(40) NOT NULL,
    color nvarchar(80) NULL,
    alloy nvarchar(30) NOT NULL,
    temper nvarchar(30) NOT NULL,
    mechanical nvarchar(80) NULL,
    ordered_quantity decimal(18,3) NOT NULL CONSTRAINT DF_order_lines_quantity DEFAULT 0,
    ordered_kg decimal(18,3) NOT NULL CONSTRAINT DF_order_lines_kg DEFAULT 0,
    produced_quantity decimal(18,3) NOT NULL CONSTRAINT DF_order_lines_produced_qty DEFAULT 0,
    produced_kg decimal(18,3) NOT NULL CONSTRAINT DF_order_lines_produced_kg DEFAULT 0,
    shipped_quantity decimal(18,3) NOT NULL CONSTRAINT DF_order_lines_shipped_qty DEFAULT 0,
    shipped_kg decimal(18,3) NOT NULL CONSTRAINT DF_order_lines_shipped_kg DEFAULT 0,
    unit_price decimal(18,6) NOT NULL CONSTRAINT DF_order_lines_price DEFAULT 0,
    line_total AS (ordered_kg * unit_price) PERSISTED,
    status nvarchar(40) NOT NULL CONSTRAINT DF_order_lines_status DEFAULT N'AÇIK',
    row_version rowversion NOT NULL,
    CONSTRAINT FK_order_lines_order FOREIGN KEY (sales_order_id) REFERENCES dbo.sales_orders(id),
    CONSTRAINT FK_order_lines_profile FOREIGN KEY (profile_id) REFERENCES dbo.profiles(id),
    CONSTRAINT FK_order_lines_die FOREIGN KEY (die_id) REFERENCES dbo.dies(id),
    CONSTRAINT UQ_order_lines_no UNIQUE (sales_order_id, line_no)
);
GO

CREATE TABLE dbo.routes (
    id bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    organization_id bigint NOT NULL,
    profile_id bigint NOT NULL,
    code nvarchar(60) NOT NULL,
    name nvarchar(160) NOT NULL,
    recipe_name nvarchar(200) NOT NULL CONSTRAINT DF_routes_recipe_name DEFAULT N'',
    production_length_mm int NOT NULL CONSTRAINT DF_routes_length DEFAULT 0,
    surface nvarchar(60) NOT NULL CONSTRAINT DF_routes_surface DEFAULT N'',
    color nvarchar(80) NOT NULL CONSTRAINT DF_routes_color DEFAULT N'',
    alloy nvarchar(30) NOT NULL CONSTRAINT DF_routes_alloy DEFAULT N'',
    temper nvarchar(30) NOT NULL CONSTRAINT DF_routes_temper DEFAULT N'',
    mechanical nvarchar(60) NOT NULL CONSTRAINT DF_routes_mechanical DEFAULT N'',
    active bit NOT NULL CONSTRAINT DF_routes_active DEFAULT 1,
    CONSTRAINT FK_routes_organization FOREIGN KEY (organization_id) REFERENCES dbo.organizations(id),
    CONSTRAINT FK_routes_profile FOREIGN KEY (profile_id) REFERENCES dbo.profiles(id),
    CONSTRAINT UQ_routes_code UNIQUE (organization_id, code)
);
GO

CREATE TABLE dbo.route_steps (
    id bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    route_id bigint NOT NULL,
    sequence_no int NOT NULL,
    operation nvarchar(60) NOT NULL,
    default_station nvarchar(80) NOT NULL,
    input_warehouse_id bigint NULL,
    output_warehouse_id bigint NULL,
    CONSTRAINT FK_route_steps_route FOREIGN KEY (route_id) REFERENCES dbo.routes(id),
    CONSTRAINT FK_route_steps_input FOREIGN KEY (input_warehouse_id) REFERENCES dbo.warehouses(id),
    CONSTRAINT FK_route_steps_output FOREIGN KEY (output_warehouse_id) REFERENCES dbo.warehouses(id),
    CONSTRAINT UQ_route_steps_sequence UNIQUE (route_id, sequence_no)
);
GO

CREATE TABLE dbo.production_orders (
    id bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    organization_id bigint NOT NULL,
    sales_order_line_id bigint NOT NULL,
    route_id bigint NOT NULL,
    production_order_no nvarchar(60) NOT NULL,
    raw_material_stock_id bigint NULL,
    planned_quantity decimal(18,3) NOT NULL,
    planned_kg decimal(18,3) NOT NULL,
    produced_quantity decimal(18,3) NOT NULL CONSTRAINT DF_prod_orders_qty DEFAULT 0,
    produced_kg decimal(18,3) NOT NULL CONSTRAINT DF_prod_orders_kg DEFAULT 0,
    status nvarchar(40) NOT NULL CONSTRAINT DF_prod_orders_status DEFAULT N'PLANLANDI',
    planned_start datetime2(0) NULL,
    planned_end datetime2(0) NULL,
    created_by bigint NOT NULL,
    created_at datetime2(0) NOT NULL CONSTRAINT DF_prod_orders_created DEFAULT SYSUTCDATETIME(),
    row_version rowversion NOT NULL,
    CONSTRAINT FK_prod_orders_organization FOREIGN KEY (organization_id) REFERENCES dbo.organizations(id),
    CONSTRAINT FK_prod_orders_order_line FOREIGN KEY (sales_order_line_id) REFERENCES dbo.sales_order_lines(id),
    CONSTRAINT FK_prod_orders_route FOREIGN KEY (route_id) REFERENCES dbo.routes(id),
    CONSTRAINT FK_prod_orders_raw_material FOREIGN KEY (raw_material_stock_id) REFERENCES dbo.stock_items(id),
    CONSTRAINT FK_prod_orders_user FOREIGN KEY (created_by) REFERENCES dbo.app_users(id),
    CONSTRAINT UQ_prod_orders_no UNIQUE (organization_id, production_order_no)
);
GO

CREATE TABLE dbo.work_orders (
    id bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    production_order_id bigint NOT NULL,
    route_step_id bigint NOT NULL,
    work_order_no nvarchar(60) NOT NULL,
    priority int NOT NULL CONSTRAINT DF_work_orders_priority DEFAULT 100,
    station nvarchar(80) NOT NULL,
    planned_quantity decimal(18,3) NOT NULL,
    planned_kg decimal(18,3) NOT NULL,
    produced_quantity decimal(18,3) NOT NULL CONSTRAINT DF_work_orders_qty DEFAULT 0,
    produced_kg decimal(18,3) NOT NULL CONSTRAINT DF_work_orders_kg DEFAULT 0,
    scrap_kg decimal(18,3) NOT NULL CONSTRAINT DF_work_orders_scrap DEFAULT 0,
    status nvarchar(40) NOT NULL CONSTRAINT DF_work_orders_status DEFAULT N'BEKLİYOR',
    actual_start datetime2(0) NULL,
    actual_end datetime2(0) NULL,
    row_version rowversion NOT NULL,
    CONSTRAINT FK_work_orders_production FOREIGN KEY (production_order_id) REFERENCES dbo.production_orders(id),
    CONSTRAINT FK_work_orders_route_step FOREIGN KEY (route_step_id) REFERENCES dbo.route_steps(id),
    CONSTRAINT UQ_work_orders_no UNIQUE (work_order_no)
);
GO

CREATE TABLE dbo.production_entries (
    id bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    work_order_id bigint NOT NULL,
    entry_type nvarchar(40) NOT NULL,
    operator_user_id bigint NOT NULL,
    shift nvarchar(30) NULL,
    die_id bigint NULL,
    lot_no nvarchar(100) NULL,
    gross_kg decimal(18,3) NOT NULL CONSTRAINT DF_prod_entries_gross DEFAULT 0,
    net_kg decimal(18,3) NOT NULL CONSTRAINT DF_prod_entries_net DEFAULT 0,
    scrap_kg AS (CASE WHEN gross_kg > net_kg THEN gross_kg - net_kg ELSE 0 END) PERSISTED,
    quantity decimal(18,3) NOT NULL CONSTRAINT DF_prod_entries_quantity DEFAULT 0,
    metre decimal(18,3) NOT NULL CONSTRAINT DF_prod_entries_metre DEFAULT 0,
    started_at datetime2(0) NOT NULL,
    ended_at datetime2(0) NULL,
    note nvarchar(max) NULL,
    created_at datetime2(0) NOT NULL CONSTRAINT DF_prod_entries_created DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_prod_entries_work_order FOREIGN KEY (work_order_id) REFERENCES dbo.work_orders(id),
    CONSTRAINT FK_prod_entries_user FOREIGN KEY (operator_user_id) REFERENCES dbo.app_users(id),
    CONSTRAINT FK_prod_entries_die FOREIGN KEY (die_id) REFERENCES dbo.dies(id)
);
GO

CREATE TABLE dbo.stock_movements (
    id bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    organization_id bigint NOT NULL,
    stock_item_id bigint NOT NULL,
    warehouse_id bigint NOT NULL,
    movement_type nvarchar(40) NOT NULL,
    direction smallint NOT NULL CHECK (direction IN (-1, 1)),
    quantity decimal(18,4) NOT NULL,
    lot_no nvarchar(100) NULL,
    sales_order_line_id bigint NULL,
    work_order_id bigint NULL,
    document_no nvarchar(80) NULL,
    movement_at datetime2(0) NOT NULL CONSTRAINT DF_stock_movements_at DEFAULT SYSUTCDATETIME(),
    created_by bigint NOT NULL,
    CONSTRAINT FK_stock_movements_organization FOREIGN KEY (organization_id) REFERENCES dbo.organizations(id),
    CONSTRAINT FK_stock_movements_item FOREIGN KEY (stock_item_id) REFERENCES dbo.stock_items(id),
    CONSTRAINT FK_stock_movements_warehouse FOREIGN KEY (warehouse_id) REFERENCES dbo.warehouses(id),
    CONSTRAINT FK_stock_movements_order_line FOREIGN KEY (sales_order_line_id) REFERENCES dbo.sales_order_lines(id),
    CONSTRAINT FK_stock_movements_work_order FOREIGN KEY (work_order_id) REFERENCES dbo.work_orders(id),
    CONSTRAINT FK_stock_movements_user FOREIGN KEY (created_by) REFERENCES dbo.app_users(id)
);
GO

CREATE TABLE dbo.packages (
    id bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    organization_id bigint NOT NULL,
    package_no nvarchar(80) NOT NULL,
    customer_id bigint NOT NULL,
    warehouse_id bigint NOT NULL,
    net_kg decimal(18,3) NOT NULL CONSTRAINT DF_packages_net DEFAULT 0,
    gross_kg decimal(18,3) NOT NULL CONSTRAINT DF_packages_gross DEFAULT 0,
    package_count int NOT NULL CONSTRAINT DF_packages_count DEFAULT 1,
    status nvarchar(40) NOT NULL CONSTRAINT DF_packages_status DEFAULT N'KASALANIYOR',
    packed_at datetime2(0) NOT NULL CONSTRAINT DF_packages_at DEFAULT SYSUTCDATETIME(),
    packed_by bigint NOT NULL,
    row_version rowversion NOT NULL,
    CONSTRAINT FK_packages_organization FOREIGN KEY (organization_id) REFERENCES dbo.organizations(id),
    CONSTRAINT FK_packages_customer FOREIGN KEY (customer_id) REFERENCES dbo.customers(id),
    CONSTRAINT FK_packages_warehouse FOREIGN KEY (warehouse_id) REFERENCES dbo.warehouses(id),
    CONSTRAINT FK_packages_user FOREIGN KEY (packed_by) REFERENCES dbo.app_users(id),
    CONSTRAINT UQ_packages_no UNIQUE (organization_id, package_no)
);
GO

CREATE TABLE dbo.package_lines (
    id bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    package_id bigint NOT NULL,
    sales_order_line_id bigint NOT NULL,
    stock_item_id bigint NOT NULL,
    lot_no nvarchar(100) NULL,
    quantity decimal(18,3) NOT NULL,
    net_kg decimal(18,3) NOT NULL,
    gross_kg decimal(18,3) NOT NULL,
    CONSTRAINT FK_package_lines_package FOREIGN KEY (package_id) REFERENCES dbo.packages(id),
    CONSTRAINT FK_package_lines_order FOREIGN KEY (sales_order_line_id) REFERENCES dbo.sales_order_lines(id),
    CONSTRAINT FK_package_lines_stock FOREIGN KEY (stock_item_id) REFERENCES dbo.stock_items(id)
);
GO

CREATE TABLE dbo.shipments (
    id bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    organization_id bigint NOT NULL,
    shipment_no nvarchar(80) NOT NULL,
    customer_id bigint NOT NULL,
    shipment_date date NOT NULL,
    vehicle_plate nvarchar(40) NULL,
    container_no nvarchar(80) NULL,
    delivery_address nvarchar(600) NULL,
    status nvarchar(40) NOT NULL CONSTRAINT DF_shipments_status DEFAULT N'HAZIRLANIYOR',
    created_by bigint NOT NULL,
    created_at datetime2(0) NOT NULL CONSTRAINT DF_shipments_created DEFAULT SYSUTCDATETIME(),
    row_version rowversion NOT NULL,
    CONSTRAINT FK_shipments_organization FOREIGN KEY (organization_id) REFERENCES dbo.organizations(id),
    CONSTRAINT FK_shipments_customer FOREIGN KEY (customer_id) REFERENCES dbo.customers(id),
    CONSTRAINT FK_shipments_user FOREIGN KEY (created_by) REFERENCES dbo.app_users(id),
    CONSTRAINT UQ_shipments_no UNIQUE (organization_id, shipment_no)
);
GO

CREATE TABLE dbo.shipment_lines (
    id bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    shipment_id bigint NOT NULL,
    package_id bigint NOT NULL,
    net_kg decimal(18,3) NOT NULL,
    gross_kg decimal(18,3) NOT NULL,
    CONSTRAINT FK_shipment_lines_shipment FOREIGN KEY (shipment_id) REFERENCES dbo.shipments(id),
    CONSTRAINT FK_shipment_lines_package FOREIGN KEY (package_id) REFERENCES dbo.packages(id),
    CONSTRAINT UQ_shipment_lines_package UNIQUE (shipment_id, package_id)
);
GO

CREATE TABLE dbo.maintenance_orders (
    id bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    organization_id bigint NOT NULL,
    maintenance_no nvarchar(80) NOT NULL,
    maintenance_type nvarchar(40) NOT NULL,
    name nvarchar(200) NOT NULL,
    operation nvarchar(80) NULL,
    station nvarchar(80) NULL,
    planned_start datetime2(0) NULL,
    planned_end datetime2(0) NULL,
    actual_start datetime2(0) NULL,
    actual_end datetime2(0) NULL,
    status nvarchar(40) NOT NULL CONSTRAINT DF_maintenance_status DEFAULT N'BAKIM BEKLİYOR',
    note nvarchar(max) NULL,
    created_by bigint NOT NULL,
    row_version rowversion NOT NULL,
    CONSTRAINT FK_maintenance_organization FOREIGN KEY (organization_id) REFERENCES dbo.organizations(id),
    CONSTRAINT FK_maintenance_user FOREIGN KEY (created_by) REFERENCES dbo.app_users(id),
    CONSTRAINT UQ_maintenance_no UNIQUE (organization_id, maintenance_no)
);
GO

CREATE TABLE dbo.attachments (
    id bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    organization_id bigint NOT NULL,
    entity_type nvarchar(80) NOT NULL,
    entity_id bigint NOT NULL,
    file_name nvarchar(260) NOT NULL,
    relative_path nvarchar(600) NOT NULL,
    content_type nvarchar(120) NULL,
    sha256 char(64) NOT NULL,
    size_bytes bigint NOT NULL,
    created_by bigint NOT NULL,
    created_at datetime2(0) NOT NULL CONSTRAINT DF_attachments_created DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_attachments_organization FOREIGN KEY (organization_id) REFERENCES dbo.organizations(id),
    CONSTRAINT FK_attachments_user FOREIGN KEY (created_by) REFERENCES dbo.app_users(id)
);
GO

CREATE TABLE dbo.audit_log (
    id bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    organization_id bigint NOT NULL,
    user_id bigint NULL,
    action nvarchar(40) NOT NULL,
    entity_type nvarchar(80) NOT NULL,
    entity_id bigint NULL,
    record_key nvarchar(160) NULL,
    before_json nvarchar(max) NULL,
    after_json nvarchar(max) NULL,
    machine_name nvarchar(160) NULL,
    created_at datetime2(0) NOT NULL CONSTRAINT DF_audit_log_created DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_audit_log_organization FOREIGN KEY (organization_id) REFERENCES dbo.organizations(id),
    CONSTRAINT FK_audit_log_user FOREIGN KEY (user_id) REFERENCES dbo.app_users(id)
);
GO

CREATE INDEX IX_sales_orders_status_delivery
ON dbo.sales_orders(organization_id, status, delivery_date);
GO
CREATE INDEX IX_sales_order_lines_status
ON dbo.sales_order_lines(sales_order_id, status);
GO
CREATE INDEX IX_work_orders_station_status
ON dbo.work_orders(station, status, priority);
GO
CREATE INDEX IX_stock_movements_balance
ON dbo.stock_movements(organization_id, stock_item_id, warehouse_id, movement_at);
GO
CREATE INDEX IX_packages_status
ON dbo.packages(organization_id, status, packed_at);
GO
CREATE INDEX IX_audit_log_entity
ON dbo.audit_log(organization_id, entity_type, entity_id, created_at DESC);
GO
