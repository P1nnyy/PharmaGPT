import neo4j from 'neo4j-driver';
import { config } from '../config/env.js';
import logger from '../utils/logger.js';

let driver;

export const initDriver = async () => {
    try {
        driver = neo4j.driver(
            config.NEO4J_URI,
            neo4j.auth.basic(config.NEO4J_USER, config.NEO4J_PASSWORD)
        );
        await driver.verifyConnectivity();
        logger.info(`Connected to Neo4j at ${config.NEO4J_URI}`);
    } catch (error) {
        logger.error(`Failed to connect to Neo4j: ${error.message}`);
        process.exit(1);
    }
};

export const getDriver = () => {
    if (!driver) {
        throw new Error('Neo4j Driver not initialized. Call initDriver() first.');
    }
    return driver;
};

export const closeDriver = async () => {
    if (driver) {
        await driver.close();
        logger.info('Neo4j Driver closed.');
    }
};
