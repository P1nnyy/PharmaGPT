// 1. Identify duplicates based on Name, Manufacturer, and Dosage Form
MATCH (p:Product)
OPTIONAL MATCH (p)-[:MANUFACTURED_BY]->(m:Manufacturer)
OPTIONAL MATCH (p)-[:HAS_FORM]->(d:DosageForm)
WITH toLower(trim(p.name)) as norm_name, 
     toLower(trim(coalesce(m.name, ''))) as norm_mfg, 
     toLower(trim(coalesce(d.name, ''))) as norm_form, 
     collect(p) as nodes, 
     count(p) as count
WHERE count > 1

// 2. Process each group of duplicates
UNWIND nodes as p
WITH norm_name, norm_mfg, norm_form, nodes, head(nodes) as survivor, tail(nodes) as duplicates

// 3. Move relationships to the survivor
FOREACH (dup IN duplicates | 
    // Move Batch relationships
    FOREACH (r IN [(dup)<-[rel:IS_BATCH_OF]-(b) | rel] | 
        MERGE (b)-[:IS_BATCH_OF]->(survivor)
        DELETE r
    )
    // Move other relationships if any (e.g. from Bill, though Bill links to Batch usually)
)

// 4. Delete duplicate nodes
FOREACH (dup IN duplicates | DETACH DELETE dup)

RETURN count(survivor) as merged_products_count
