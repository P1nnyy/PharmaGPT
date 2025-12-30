import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';

// Load .env from root (two levels up from src/config)
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootPath = path.resolve(__dirname, '../../../');

dotenv.config({ path: path.join(rootPath, '.env') });

export const config = {
    PORT: process.env.PORT || 8000,
    NEO4J_URI: process.env.NEO4J_URI || 'bolt://localhost:7687',
    NEO4J_USER: process.env.NEO4J_USER || 'neo4j',
    NEO4J_PASSWORD: process.env.NEO4J_PASSWORD || 'password',
    GOOGLE_API_KEY: process.env.GOOGLE_API_KEY,
};
