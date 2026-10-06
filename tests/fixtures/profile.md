# Source workbook profile

Profiled read-only from `data/source/*.xlsx` using the workbook XML and shared-string tables. The six files each contain one sheet, a single header row, no title/blank rows, and no visible merged-cell regions. All six have a header plus records; no source file was modified.

| File / sheet | Records | Columns | Notable content |
|---|---:|---:|---|
| customers.xlsx / Customers | 32 | 12 | Customer ID, names/contact, city/state/country, JoinDate, LoyaltyTier, PreferredMetal, MarketingOptIn. State has 1 blank; LoyaltyTier 4 values; City 10. |
| employees.xlsx / Employees | 14 | 12 | Employee ID, names, job/department, HireDate, AnnualSalaryUSD, EmploymentType, Status, ManagerID, contact. ManagerID has 1 blank; Department 5 values. |
| products.xlsx / Products | 40 | 12 | SKU, ProductName, Category, Material, Gemstone, WeightGrams, CostPriceUSD, RetailPriceUSD, MarginPct, StockQty, ReorderLevel, SupplierID. Category 6 values; StockQty 16; SupplierID 9. |
| purchases.xlsx / Purchases | 40 | 11 | PONumber, OrderDate, SupplierID, SKU, QtyOrdered, UnitCostUSD, TotalCostUSD, Status, QtyReceived, ReceivedDate, ApprovedBy. ReceivedDate has 4 blanks; Status 4 values. |
| sales.xlsx / Sales | 65 | 11 | InvoiceNo, SaleDate, CustomerID, SKU, Quantity, UnitPriceUSD, DiscountPct, LineTotalUSD, PaymentMethod, Channel, SoldBy. InvoiceNo has 54 distinct values (repeated invoice numbers); Channel 2 values; PaymentMethod 6. |
| suppliers.xlsx / Suppliers | 10 | 10 | SupplierID, SupplierName, Country, ContactPerson, ContactEmail, Phone, Specialty, PaymentTerms, QualityRating, PartnerSince. PaymentTerms 4 values. |

**Likely links to verify in the application:** Sales.CustomerID → Customers.CustomerID; Sales.SKU → Products.SKU; Sales.SoldBy → Employees.EmployeeID; Purchases.SupplierID → Suppliers.SupplierID; Purchases.SKU → Products.SKU; Purchases.ApprovedBy → Employees.EmployeeID; Products.SupplierID → Suppliers.SupplierID. Employees.ManagerID is a self-reference. Sales invoices are line-level; do not count InvoiceNo rows as invoices without distinct counting.

**Type and data caveats:** Excel dates are stored as serials (for example, Sales.SaleDate values near 46035), so they must be converted using workbook date semantics. Numeric price fields are decimal-valued. DiscountPct and MarginPct are proportions (e.g. 0.05 = 5%). Some formula-derived fields are present as values in the workbook (Sales.LineTotalUSD, Products.MarginPct, Purchases.TotalCostUSD); test cached-value ingestion explicitly. Excel styling and XML show ordinary headers; this profile does not independently validate formula recalculation or business arithmetic. The source has relatively few rows, suitable for independently computed exact answer checks.

**Coverage seed:** totals and averages of Sales.LineTotalUSD / Quantity, category and channel aggregations, monthly SaleDate groups, top product/customer/employee, product stock against ReorderLevel with supplier join, pending purchase totals by supplier, and loyalty tiers joined to sales. Use independent calculations from original source workbook values for the golden set; do not source expected values from the app.
