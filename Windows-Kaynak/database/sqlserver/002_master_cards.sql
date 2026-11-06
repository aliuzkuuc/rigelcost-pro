-- RIGEL FIRMA / FIRMA_ILGILI / KALIP ana kart karşılıkları.
ALTER TABLE dbo.customers ADD
    short_name nvarchar(120) NULL,
    sector nvarchar(120) NULL,
    district nvarchar(100) NULL,
    postal_code nvarchar(20) NULL,
    phone2 nvarchar(60) NULL,
    fax nvarchar(60) NULL,
    email2 nvarchar(180) NULL,
    accounting_code nvarchar(80) NULL,
    bank_name nvarchar(160) NULL,
    notes nvarchar(max) NULL,
    order_note nvarchar(max) NULL,
    production_note nvarchar(max) NULL,
    general_warning nvarchar(max) NULL,
    is_supplier bit NOT NULL CONSTRAINT DF_customers_is_supplier DEFAULT 0,
    is_subcontractor bit NOT NULL CONSTRAINT DF_customers_is_subcontractor DEFAULT 0;
GO

CREATE TABLE dbo.customer_contacts (
    id bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
    organization_id bigint NOT NULL,
    customer_id bigint NOT NULL,
    name nvarchar(180) NOT NULL,
    role nvarchar(120) NULL,
    phone1 nvarchar(60) NULL,
    phone2 nvarchar(60) NULL,
    email nvarchar(180) NULL,
    active bit NOT NULL CONSTRAINT DF_customer_contacts_active DEFAULT 1,
    created_at datetime2(0) NOT NULL CONSTRAINT DF_customer_contacts_created DEFAULT SYSUTCDATETIME(),
    created_by nvarchar(160) NULL,
    CONSTRAINT FK_customer_contacts_organization FOREIGN KEY (organization_id) REFERENCES dbo.organizations(id),
    CONSTRAINT FK_customer_contacts_customer FOREIGN KEY (customer_id) REFERENCES dbo.customers(id)
);
GO

CREATE INDEX IX_customer_contacts_customer
ON dbo.customer_contacts(organization_id, customer_id, active);
GO

ALTER TABLE dbo.dies ADD
    tenefer_no nvarchar(80) NULL,
    tenefer_type nvarchar(100) NULL;
GO
