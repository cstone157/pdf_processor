import chromadb

# Initialize the client (in-memory)
client = chromadb.Client()

# Create a collection
collection = client.create_collection("my_documents")

# Add text documents (Chroma handles the vectorization)
collection.add(
    documents=["This is a document about cats", "This is a document about dogs"],
    metadatas=[{"category": "animal"}, {"category": "animal"}],
    ids=["doc1", "doc2"]
)

# Query for similar documents
results = collection.query(
    query_texts=["Tell me about pets"],
    n_results=2
)
print(results)