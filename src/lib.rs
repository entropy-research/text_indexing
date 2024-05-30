pub mod file;
pub mod indexes;
pub mod intelligence;
pub mod repository;
pub mod sync_handle;
pub mod symbol;
pub mod text_range;
pub mod search;
pub mod schema;
pub mod snippet;
pub mod content_document;

pub use file::File;
pub use indexes::{Indexes, Indexable};
pub use repository::Repository;
pub use sync_handle::SyncHandle;



// use anyhow::Result;
// use std::path::Path;