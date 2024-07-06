# Initia Blockchain Data Processor

## Overview

This project is designed to process blockchain data for the Initia network. It includes scripts for downloading, decoding, and analyzing transaction data. The project uses PostgreSQL for data storage and is containerized using Docker and Docker Compose for easy setup and deployment.

## Table of Contents

- [Requirements](#requirements)
- [Setup](#setup)
  - [Docker Installation](#docker-installation)
  - [Building and Running the Project](#building-and-running-the-project)
- [Configuration](#configuration)
- [Scripts](#scripts)
- [Environment Variables](#environment-variables)
- [Notes](#notes)

## Requirements

- Docker
- Docker Compose

## Setup

### Docker Installation

1. **Install Docker**:
   Follow the instructions on the [Docker website](https://docs.docker.com/get-docker/) to install Docker on your system.

2. **Install Docker Compose**:
   Docker Compose is typically included with Docker Desktop installations on Windows and macOS. For Linux, follow the [Docker Compose installation instructions](https://docs.docker.com/compose/install/).

### Building and Running the Project

1. **Clone the repository**:
   ```sh
   git clone https://github.com/yourusername/initia-blockchain-processor.git
   cd initia-blockchain-processor
Build and run the Docker containers:

sh

    docker-compose up --build

    This command will build the Docker image for the application and start the PostgreSQL and application services.

Configuration

The application configuration is managed via environment variables. These are defined in the Dockerfile and docker-compose.yml files.
Scripts

The following scripts are included in the project:

    main.py: The main script that coordinates the downloading, decoding, and analysis of blockchain data.
    get_all_validators.py: Retrieves all validators from a REST endpoint.
    get_all_validators_votes.py: Checks if validators voted and records their votes.
    get_db_stats.py: Prints statistics from the database.
    get_percent_msg_interactions.py: Analyzes the percentage of message interactions over a block period.
    get_relayers.py: Retrieves relayers who have relayed transactions.
    get_total_fees_over_time.py: Calculates total fees and gas used over time.
    get_txs_per_day.py: Counts the number of transactions per day.
    get_unjails.py: Retrieves validators who have been unjailed.
    get_votes.py: Retrieves addresses that voted on specific proposals.
    most_active_contracts.py: Analyzes the most active smart contracts based on interactions.

Environment Variables

The following environment variables are used to configure the application:

    COSMOS_PROTO_DECODE_BINARY: The binary used for decoding protobuf messages.
    COSMOS_PROTO_DECODE_LIMIT: The maximum number of transactions to decode at once.
    COSMOS_PROTO_DECODE_BLOCK_LIMIT: The maximum number of blocks to decode at once.
    TX_AMINO_LENGTH_CUTTOFF_LIMIT: The cutoff limit for the length of amino transactions.
    WALLET_PREFIX: The prefix for wallet addresses.
    VALOPER_PREFIX: The prefix for validator operator addresses.
    TASK: The task to perform (download, decode, missing, or sync).
    DB_NAME: The name of the PostgreSQL database.
    DB_USER: The PostgreSQL database user.
    DB_PASSWORD: The PostgreSQL database password.
    DB_HOST: The PostgreSQL database host.
    DB_PORT: The PostgreSQL database port.
    CHAINID: The chain ID of the Initia network.

Notes

    Ensure PostgreSQL is properly configured:
    The PostgreSQL service is defined in the docker-compose.yml file. Make sure the database connection parameters (DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, and DB_PORT) match the ones specified in the docker-compose.yml file.

    Data Persistence:
    The PostgreSQL data is persisted using Docker volumes. This ensures that data is not lost when the container is stopped or removed.

    Scripts Usage:
    Each script in the project is designed to perform a specific task related to blockchain data processing. You can run these scripts individually or coordinate them using the main.py script.
Original by [Github](https://github.com/Reecepbcups/interchain-indexer)
