-- MAXCAPITAL Bot - Database Initialization

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create user_memory table
CREATE TABLE IF NOT EXISTS user_memory (
    user_id BIGINT PRIMARY KEY,
    full_name TEXT,
    phone TEXT,
    selected_service TEXT,
    conversation_history JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create documents table for RAG
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
    content_text TEXT NOT NULL,
    embedding vector(1536),
    file_type TEXT,
    file_size INTEGER,
    drive_file_id TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create index for vector similarity search
CREATE INDEX IF NOT EXISTS documents_embedding_idx 
ON documents USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Create index for user lookups
CREATE INDEX IF NOT EXISTS idx_user_memory_phone ON user_memory(phone);
CREATE INDEX IF NOT EXISTS idx_user_memory_created_at ON user_memory(created_at);

-- Create index for document searches
CREATE INDEX IF NOT EXISTS idx_documents_filename ON documents(filename);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at);


