use std::path::Path;
use tantivy::schema::Field;
use tantivy::{Index, IndexReader, collector::TopDocs, query::QueryParser};
use anyhow::Result;
use serde::{Deserialize, Serialize};

use crate::content_document::ContentDocument;
use crate::intelligence::code_navigation::{CodeNavigationContext, FileSymbols, Token};
use crate::schema::build_schema;
use crate::symbol::SymbolLocations;

#[derive(Debug, Serialize, Deserialize)]
pub struct SearchResult {
    pub path: String,
    pub line_number: usize,
    pub column: usize,
    pub context: String,
}

pub struct Searcher {
    index: Index,
    reader: IndexReader,
    path_field: Field,
    content_field: Field,
    line_end_indices_field: Field,
    lang_field: Field, // Added lang field
    symbol_locations_field: Field,
}

impl Searcher {
    pub fn new(index_path: &Path) -> Result<Self> {
        let index = Index::open_in_dir(index_path)?;
        let reader = index.reader()?;
        let schema = build_schema();
        let path_field = schema.get_field("path").unwrap();
        let content_field = schema.get_field("content").unwrap();
        let line_end_indices_field = schema.get_field("line_end_indices").unwrap();
        let lang_field = schema.get_field("lang").unwrap(); // Added lang field
        let symbol_locations_field = schema.get_field("symbol_locations").unwrap();

        Ok(Self {
            index,
            reader,
            path_field,
            content_field,
            line_end_indices_field,
            lang_field,
            symbol_locations_field,
        })
    }

    pub fn text_search(&self, query_str: &str) -> Result<Vec<SearchResult>> {
        let searcher = self.reader.searcher();
        let query_parser = QueryParser::for_index(&self.index, vec![self.content_field]);

        let query = query_parser.parse_query(query_str)?;
        let top_docs = searcher.search(&query, &TopDocs::with_limit(10))?;

        let mut results = Vec::new();
        for (_score, doc_address) in top_docs {
            let retrieved_doc = searcher.doc(doc_address)?;

            let path = match retrieved_doc.get_first(self.path_field) {
                Some(path_field) => path_field.as_text().unwrap().to_string(),
                None => {
                    println!("Debug: Path field is missing");
                    continue;
                }
            };

            let content = match retrieved_doc.get_first(self.content_field) {
                Some(content_field) => content_field.as_text().unwrap().to_string(),
                None => {
                    println!("Debug: Content field is missing");
                    continue;
                }
            };

            let line_end_indices_field = retrieved_doc.get_first(self.line_end_indices_field);
            println!("Debug: line_end_indices_field - {:?}", line_end_indices_field);

            let line_end_indices: Vec<u32> = match line_end_indices_field {
                Some(field) => {
                    match field.as_bytes() {
                        Some(bytes) => {
                            bytes.chunks_exact(4).map(|c| {
                                u32::from_le_bytes([c[0], c[1], c[2], c[3]])
                            }).collect()
                        }
                        None => {
                            println!("Debug: Failed to get bytes");
                            continue;
                        }
                    }
                }
                None => {
                    println!("Debug: Line end indices field is missing");
                    continue;
                }
            };

            println!("Debug: Line end indices - {:?}", line_end_indices);

            for (line_number, window) in line_end_indices.windows(2).enumerate() {
                if let [start, end] = *window {
                    let line = &content[start as usize..end as usize];

                    if line.contains(query_str) {
                        let column = line.find(query_str).unwrap();
                        let context_start = if line_number >= 3 { line_number - 3 } else { 0 };
                        let context_end = usize::min(line_number + 3, line_end_indices.len() - 1);
                        let context: String = line_end_indices[context_start..=context_end]
                            .windows(2)
                            .map(|w| {
                                let start = w[0] as usize;
                                let end = w[1] as usize;
                                &content[start..end]
                            })
                            .collect::<Vec<_>>()
                            .join("\n");

                        results.push(SearchResult {
                            path: path.clone(),
                            line_number,
                            column,
                            context,
                        });
                    }
                }
            }
        }

        Ok(results)
    }

    pub fn load_all_documents(&self, lang: &str) -> Result<Vec<ContentDocument>> {
        let searcher = self.reader.searcher();

        let mut documents = Vec::new();
        for segment_reader in searcher.segment_readers() {
            let store_reader = segment_reader.get_store_reader(0)?;
            let alive_bitset = segment_reader.alive_bitset();

            for doc in store_reader.iter(alive_bitset) {
                let doc = doc?;
                let lang_field_value = doc.get_first(self.lang_field)
                    .and_then(|f| f.as_text())
                    .unwrap_or("").to_lowercase();

                // println!("{:?} {:?}", lang_field_value, lang);

                if lang_field_value == lang {
                    let content = doc.get_first(self.content_field)
                        .and_then(|f| f.as_text())
                        .unwrap_or("")
                        .to_string();

                    let relative_path = doc.get_first(self.path_field)
                        .and_then(|f| f.as_text())
                        .unwrap_or("")
                        .to_string();

                    let line_end_indices: Vec<u32> = doc.get_first(self.line_end_indices_field)
                        .and_then(|f| f.as_bytes())
                        .unwrap_or(&[])
                        .chunks_exact(4)
                        .map(|c| u32::from_le_bytes([c[0], c[1], c[2], c[3]]))
                        .collect();

                    let symbol_locations: SymbolLocations = doc.get_first(self.symbol_locations_field)
                        .and_then(|f| f.as_bytes())
                        .and_then(|b| bincode::deserialize(b).ok())
                        .unwrap_or_default();

                    // println!("{:?}", symbol_locations);

                    documents.push(ContentDocument {
                        content,
                        lang: Some(lang.to_string()),
                        relative_path,
                        line_end_indices,
                        symbol_locations,
                    });
                }
            }
        }

        Ok(documents)
    }


    pub fn token_info(&self, lang: &str, relative_path: &str, start_byte: usize, end_byte: usize) -> Result<Vec<FileSymbols>> {
        let all_docs = self.load_all_documents(lang)?;
        
        // Find the source document based on the provided relative path
        let source_document_idx = all_docs.iter().position(|doc| doc.relative_path == relative_path)
            .ok_or(anyhow::anyhow!("Source document not found"))?;
        
        let doc = all_docs.get(source_document_idx).unwrap();

        println!("{:?}", doc.content);

        let token = Token {
            relative_path,
            start_byte,
            end_byte,
        };

        let context = CodeNavigationContext {
            token,
            all_docs: &all_docs,
            source_document_idx,
            snipper: None, // Provide a snipper if needed for snippet generation
        };

        let data = context.token_info();
        Ok(data)
    }
}