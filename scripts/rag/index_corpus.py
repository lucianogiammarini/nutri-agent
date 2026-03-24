"""
Standalone script to index the GAPA corpus into the vector database.

Usage:
    python scripts/rag/index_corpus.py
"""

import os
import sys

# Correct path to find 'src' from 'scripts/rag/'
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from dotenv import load_dotenv
from src.infrastructure.dependency_container import DependencyContainer

def main():
    load_dotenv()
    container = DependencyContainer()
    
    corpus_file = container.corpus_path

    if not os.path.exists(corpus_file):
        print(f"❌ File '{corpus_file}' not found.")
        print(f"   Please ensure the corpus file is in {corpus_file}")
        sys.exit(1)

    print("=" * 60)
    print("📚 GAPA Corpus Indexer - Vector Database")
    print(f"   Using: {corpus_file}")
    print("=" * 60)

    # Step 1: Split text into chunks
    print("\n📄 Step 1: Splitting text into chunks...")
    from src.infrastructure.adapters.text_splitter import TextSplitter

    # Use default settings from container if possible, but here we can customize
    splitter = TextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_file(corpus_file)
    print(f"   ✅ Generated {len(chunks)} chunks")

    # Show a sample
    if chunks:
        print(f"\n   📎 Sample chunk (#{chunks[0].chunk_index}):")
        preview = chunks[0].text[:150].replace('\n', ' ')
        print(f"   \"{preview}...\"")

    # Step 2: Store in ChromaDB
    print("\n🗄️  Step 2: Storing chunks in ChromaDB...")
    repo = container.vector_repository
    
    repo.clear()
    stored = repo.add_chunks(chunks)
    print(f"   ✅ Stored {stored} chunks in vector database")
    print(f"   📁 Database location: {container.chroma_path}")

    # Step 3: Test with a sample query
    print("\n🔍 Step 4: Testing with a sample query...")
    test_query = "alimentación saludable"
    results = repo.search(test_query, top_k=3)

    print(f"   Query: \"{test_query}\"")
    print(f"   Results: {len(results)} chunks found\n")

    for i, chunk in enumerate(results):
        preview = chunk.text[:120].replace('\n', ' ')
        print(f"   [{i+1}] Score: {chunk.score} | \"{preview}...\"")

    print("\n" + "=" * 60)
    print("✅ Indexing complete!")
    print(f"   Total chunks in DB: {repo.count()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
