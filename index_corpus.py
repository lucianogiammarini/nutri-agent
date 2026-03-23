"""
Standalone script to index the GAPA corpus into the vector database.

Usage:
    python index_corpus.py

This will:
1. Read gapa_clean_corpus.txt
2. Split it into chunks
3. Generate embeddings using sentence-transformers
4. Store everything in ChromaDB (chroma_db/ directory)

After indexing, you can search using the Flask API:
    curl -X POST http://localhost:5000/rag/search \
         -H "Content-Type: application/json" \
         -d '{"query": "¿Cuánta agua debo tomar por día?", "top_k": 3}'
"""

import os
import sys


def main():
    corpus_file = "gapa_clean_corpus.txt"

    if not os.path.exists(corpus_file):
        print(f"❌ File '{corpus_file}' not found.")
        print("   Run script.py first to download and process the PDF.")
        sys.exit(1)

    print("=" * 60)
    print("📚 GAPA Corpus Indexer - Vector Database")
    print("=" * 60)

    # Step 1: Split text into chunks
    print("\n📄 Step 1: Splitting text into chunks...")
    from src.infrastructure.adapters.text_splitter import TextSplitter

    splitter = TextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_file(corpus_file)
    print(f"   ✅ Generated {len(chunks)} chunks")

    # Show a sample
    if chunks:
        print(f"\n   📎 Sample chunk (#{chunks[0].chunk_index}):")
        preview = chunks[0].text[:150].replace('\n', ' ')
        print(f"   \"{preview}...\"")

    # Step 2: Store in ChromaDB
    print("\n🗄️  Step 2: Storing chunks in ChromaDB (this may take a moment on first run)...")
    from src.infrastructure.repositories.chroma_vector_repository import ChromaVectorRepository

    repo = ChromaVectorRepository(persist_directory="chroma_db")
    repo.clear()
    stored = repo.add_chunks(chunks)
    print(f"   ✅ Stored {stored} chunks in vector database")
    print(f"   📁 Database location: chroma_db/")

    # Step 3: Test with a sample query
    print("\n🔍 Step 3: Testing with a sample query...")
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
    print("\n💡 You can now search using the Flask API:")
    print('   curl -X POST http://localhost:5000/rag/search \\')
    print('        -H "Content-Type: application/json" \\')
    print('        -d \'{"query": "¿Cuánta agua debo tomar?", "top_k": 3}\'')
    print("=" * 60)


if __name__ == "__main__":
    main()
