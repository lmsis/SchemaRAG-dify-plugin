# LM DB Schema RAG Plugin Usage

A Dify plugin for building database schema RAG: it analyzes database structure and uploads it to a Dify knowledge base.

## Features

- Automatically analyzes MySQL/PostgreSQL (and other supported) database structures
- Generates data dictionary documentation
- Uploads to a Dify knowledge base
- Ships with a ready-to-use Text2SQL tool

## Required configuration

- **Dataset API Key**: Dify knowledge base API key
- **Database Type**: e.g. MySQL / PostgreSQL
- **Database Host**: database host
- **Database Port**: port (default 3306 for MySQL)
- **Database User**: username
- **Database Password**: password
- **Database Name**: database name
- **Dify Base URL**: Dify API base URL (default: `https://api.dify.ai/v1`)

## How to use

Configure the provider in Dify, run the schema build, then attach the generated dataset IDs to tools such as Text2SQL or Text2Data. See the main [README](README.md) for full workflow details.

## Self-hosted: install from GitHub / signature error

Installing the `.difypkg` from this repo’s releases may fail with **bad signature** if Dify has plugin verification enabled. Options: (1) set `FORCE_VERIFYING_SIGNATURE=false` for trusted internal builds — [docs/GITHUB_INSTALL_PLUGIN.md](docs/GITHUB_INSTALL_PLUGIN.md#erro-bad-signature-plugin-verification); (2) keep verification on and **sign** packages with your key pair — [docs/PLUGIN_SIGNING.md](docs/PLUGIN_SIGNING.md).
