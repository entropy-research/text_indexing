use std::path::Path;
use tantivy::{schema::Schema, IndexWriter, doc};
use anyhow::Result;
use async_trait::async_trait;
use tokio::fs;
use tokio::task::spawn_blocking;
use futures::future::BoxFuture;
use std::collections::HashSet;
use crate::{indexes::Indexable, sync_handle::SyncHandle};
use crate::intelligence::{TreeSitterFile, TSLanguage};
use crate::symbol::SymbolLocations;
use crate::schema::build_schema; // Import the schema module

pub struct File {
    pub schema: Schema,
    pub path_field: tantivy::schema::Field,
    pub content_field: tantivy::schema::Field,
    pub symbol_locations_field: tantivy::schema::Field,
    pub symbols_field: tantivy::schema::Field,
    pub line_end_indices_field: tantivy::schema::Field,
    pub lang_field: tantivy::schema::Field,
}

impl File {
    pub fn new() -> Self {
        let schema = build_schema();
        let path_field = schema.get_field("path").unwrap();
        let content_field = schema.get_field("content").unwrap();
        let symbol_locations_field = schema.get_field("symbol_locations").unwrap();
        let symbols_field = schema.get_field("symbols").unwrap();
        let line_end_indices_field = schema.get_field("line_end_indices").unwrap();
        let lang_field = schema.get_field("lang").unwrap();

        Self {
            schema,
            path_field,
            content_field,
            symbol_locations_field,
            symbols_field,
            line_end_indices_field,
            lang_field
        }
    }

    fn detect_language(path: &Path) -> &'static str {
        let extension = path.extension().and_then(std::ffi::OsStr::to_str).unwrap_or("");
        TSLanguage::from_extension(extension).unwrap_or("plaintext")
    }
}

#[async_trait]
impl Indexable for File {
    async fn index_repository(&self, handle: &SyncHandle, root_path: &Path, writer: &IndexWriter) -> Result<()> {
        traverse_and_index_files(root_path, writer, &self.schema, self.path_field, self.content_field, self.symbol_locations_field, self.symbols_field, self.line_end_indices_field, self.lang_field).await
    }

    fn schema(&self) -> Schema {
        self.schema.clone()
    }
}

fn traverse_and_index_files<'a>(
    path: &'a Path,
    writer: &'a IndexWriter,
    schema: &'a Schema,
    path_field: tantivy::schema::Field,
    content_field: tantivy::schema::Field,
    symbol_locations_field: tantivy::schema::Field,
    symbols_field: tantivy::schema::Field,
    line_end_indices_field: tantivy::schema::Field,
    lang_field: tantivy::schema::Field,
) -> BoxFuture<'a, Result<()>> {
    Box::pin(async move {
        let mut entries = fs::read_dir(path).await?;
        while let Some(entry) = entries.next_entry().await? {
            let path = entry.path();
            if path.is_dir() {
                traverse_and_index_files(&path, writer, schema, path_field, content_field, symbol_locations_field, symbols_field, line_end_indices_field, lang_field).await?;
            } else if path.is_file() {
                let path_clone = path.clone();
                let content = spawn_blocking(move || std::fs::read(&path_clone)).await??;

                let content_str = match String::from_utf8(content) {
                    Ok(content_str) => content_str,
                    Err(_) => continue, // Skip if the content is not valid UTF-8
                };

                let lang_str = File::detect_language(&path);

                if lang_str == "plaintext" {
                    continue;
                }

                let symbol_locations: SymbolLocations = {
                    let scope_graph = TreeSitterFile::try_build(content_str.as_bytes(), lang_str)
                        .and_then(TreeSitterFile::scope_graph);

                    match scope_graph {
                        Ok(graph) => {
                            
                            SymbolLocations::TreeSitter(graph)
                        },
                        Err(_) => SymbolLocations::Empty,
                    }
                };
                

                // Flatten the list of symbols into a string with just text
                let symbols = symbol_locations
                    .list()
                    .iter()
                    .map(|sym| content_str[sym.range.start.byte..sym.range.end.byte].to_owned())
                    .collect::<HashSet<_>>()
                    .into_iter()
                    .collect::<Vec<_>>()
                    .join("\n");

                // println!("{:?}", path);
                // println!("Debug: TreeSitterFile Graph - {:?}", symbols);

                // Collect line end indices as bytes
                let line_end_indices = content_str
                    .match_indices('\n')
                    .flat_map(|(i, _)| u32::to_le_bytes(i as u32))
                    .collect::<Vec<_>>();

                // Debugging statement to print line end indices
                // println!("Debug: line_end_indices - {:?}", line_end_indices);

                let doc = tantivy::doc!(
                    path_field => path.to_string_lossy().to_string(),
                    content_field => content_str,
                    symbol_locations_field => bincode::serialize(&symbol_locations).unwrap(),
                    symbols_field => symbols,
                    line_end_indices_field => line_end_indices,
                    lang_field => lang_str.to_string(),
                );

                writer.add_document(doc)?;
            }
        }
        Ok(())
    })
}
