use anyhow::Result;
use std::path::Path;
use retreival::{indexes::Indexes, search::Searcher};

#[tokio::main]
async fn main() -> Result<()> {
    let root_path = Path::new(".");
    // println!("{}", root_path.display());
    let index_path = Path::new("./index");
    
    let buffer_size_per_thread = 15_000_000;
    let num_threads = 4;

    // let indexes = Indexes::new(&index_path, buffer_size_per_thread, num_threads).await?;
    // indexes.index(root_path).await?;

    // Create a searcher and perform a search
    let searcher = Searcher::new(&index_path)?;
    let result = searcher.token_info("rust", "./src/schema.rs", 0, 0);
    println!("{:?}", result);
    // let results = searcher.load_all_documents("rust");
    // let results = searcher.text_search("searcher")?;

    // // Print out the results
    // for result in results {
    //     println!(
    //         "File: {}, Line: {}, Column: {}, Context: {}",
    //         result.path, result.line_number, result.column, result.context
    //     );
    // }

    Ok(())
}