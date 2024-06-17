use anyhow::Result;
use std::path::Path;
use retreival::{indexes::Indexes, search::Searcher};
use serde_json::json;

#[tokio::main]
async fn main() -> Result<()> {
    let root_path = Path::new("/Users/arnav/Desktop/devon/Devon");
    // println!("{}", root_path.display());
    let index_path = Path::new("/Users/arnav/Desktop/devon/Devon/index");
    
    let buffer_size_per_thread = 15_000_000;
    let num_threads = 4;

    let indexes = Indexes::new(&index_path, buffer_size_per_thread, num_threads).await?;
    indexes.index(root_path).await?;

    // // // // Create a searcher and perform a search
    let searcher = Searcher::new(&index_path)?;

    // let result = searcher.token_info("/Users/arnav/Desktop/r2/retreival/src/main.rs", 14, 18, 25);
    // match result {
    //     Ok(token_info) => println!("{}", retreival::search::Searcher::format_token_info(token_info)),
    //     Err(e) => println!("Error retrieving token info: {}", e),
    // }

    let result = searcher.text_search("Agent", true)?;
    println!("{}", retreival::search::Searcher::format_search_results(result));

    // let result = searcher.get_hoverable_ranges("/Users/arnav/Desktop/devon/Devon/devon_agent/tools/edittools.py")?;
    // println!("{}", json!(retreival::search::Searcher::format_hoverable_ranges(result)).to_string());

    // println!("-");
    // // Print out the results
    



    Ok(())
}
