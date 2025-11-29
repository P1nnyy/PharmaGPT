// 1. Constraints & Indexes
// Ensure Product names are unique
CREATE CONSTRAINT product_name_unique IF NOT EXISTS FOR (p:Product) REQUIRE p.name IS UNIQUE;

// Ensure Batch numbers are unique
CREATE CONSTRAINT batch_number_unique IF NOT EXISTS FOR (b:InventoryBatch) REQUIRE b.batch_number IS UNIQUE;

// Ensure Bill IDs are unique
CREATE CONSTRAINT bill_id_unique IF NOT EXISTS FOR (b:Bill) REQUIRE b.id IS UNIQUE;

// New Entities Constraints
CREATE CONSTRAINT manufacturer_name_unique IF NOT EXISTS FOR (m:Manufacturer) REQUIRE m.name IS UNIQUE;
CREATE CONSTRAINT composition_name_unique IF NOT EXISTS FOR (c:Composition) REQUIRE c.name IS UNIQUE;
CREATE CONSTRAINT category_name_unique IF NOT EXISTS FOR (cat:Category) REQUIRE cat.name IS UNIQUE;

// 2. Fulltext Search Index
// Create index for fuzzy search on Product names and Composition names
CREATE FULLTEXT INDEX productNames IF NOT EXISTS FOR (n:Product|Composition) ON EACH [n.name];

// 3. Schema Evolution (Sample Data / Migration)
// Create default Manufacturer and Category if they don't exist and link orphan products
MERGE (m:Manufacturer {name: "Generic Pharma Co."})
MERGE (c:Category {name: "General"})
WITH m, c
MATCH (p:Product)
WHERE NOT (p)-[:MANUFACTURED_BY]->()
MERGE (p)-[:MANUFACTURED_BY]->(m)
MERGE (p)-[:IS_CATEGORY]->(c);

// 4. Example: Adding Salt Composition (Manual Step for existing data)
// MATCH (p:Product {name: "Dolo 650"})
// MERGE (c:Composition {name: "Paracetamol"})
// MERGE (p)-[:CONTAINS_SALT]->(c);

// 5. Dosage Form Constraints [NEW]
// Ensure Dosage Form names are unique
CREATE CONSTRAINT dosage_form_name_unique IF NOT EXISTS FOR (d:DosageForm) REQUIRE d.name IS UNIQUE;

// 6. Dosage Form Migration (Schema Evolution) [NEW]
// Link all existing products that don't have a form to a default "Tablet" form
MATCH (p:Product)
WHERE NOT (p)-[:HAS_FORM]->()
MERGE (d:DosageForm {name: "Tablet"})
MERGE (p)-[:HAS_FORM]->(d);