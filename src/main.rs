use anyhow::Result;
use std::path::Path;
use retreival::{indexes::Indexes, search::Searcher};

#[tokio::main]
async fn main() -> Result<()> {
    let root_path = Path::new("/Users/arnav/Desktop/r2/retreival");
    // println!("{}", root_path.display());
    let index_path = Path::new("/Users/arnav/Desktop/r2/retreival/index");
    
    let buffer_size_per_thread = 15_000_000;
    let num_threads = 4;

    let indexes = Indexes::new(&index_path, buffer_size_per_thread, num_threads).await?;
    indexes.index(root_path).await?;

    // // // // Create a searcher and perform a search
    let searcher = Searcher::new(&index_path)?;
    // let result = searcher.token_info("rust", "/Users/arnav/Desktop/r2/retreival/src/main.rs", 18, 19, 27);
    // println!("{:?}", result);
    // // // // let results = searcher.load_all_documents("rust");
    let result = searcher.text_search("indexes")?;

    // println!("-");
    // // Print out the results
    for resul in result {
        println!("{:?}", resul.path);
        // println!("{:?}", resul.context);
    }


    Ok(())
}
