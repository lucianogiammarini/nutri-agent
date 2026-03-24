
import os
import sys

# Correct path to find 'src' from 'scripts/rag/'
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from dotenv import load_dotenv
from src.infrastructure.dependency_container import DependencyContainer

def reindex():
    load_dotenv()
    container = DependencyContainer()
    
    # Get the use case from the controller
    controller = container.rag_controller
    use_case = controller.index_corpus_use_case
    
    # Use the path defined in the container
    corpus_path = container.corpus_path
    
    if not os.path.exists(corpus_path):
        print(f"Error: {corpus_path} not found")
        return

    print(f"Re-indexing {corpus_path} with new chunking settings...")
    result = use_case.execute(corpus_path, clear_existing=True)
    
    if result['success']:
        print(f"Success! {result['data']['chunks_created']} chunks created.")
        print(f"Total chunks in DB: {result['data']['total_in_db']}")
    else:
        print(f"Failed: {result['error']}")

if __name__ == "__main__":
    reindex()
