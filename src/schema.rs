use tantivy::schema::{Schema, SchemaBuilder, TEXT, STORED, BytesOptions, FAST};

pub fn build_schema() -> Schema {
    let mut schema_builder = SchemaBuilder::default();
    schema_builder.add_text_field("path", TEXT | STORED | FAST);
    schema_builder.add_text_field("content", TEXT | STORED);
    schema_builder.add_bytes_field("symbol_locations", STORED);
    schema_builder.add_bytes_field("line_end_indices", BytesOptions::default().set_stored());
    schema_builder.add_text_field("symbols", TEXT | STORED);
    schema_builder.add_text_field("lang", TEXT | STORED | FAST);
    schema_builder.build()
}