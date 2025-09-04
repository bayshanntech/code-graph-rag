# CPDValet API RAG MCP Server

## Background

This is a MPC server that runs a https://github.com/memgraph/ai-toolkit Graph Database to provide a RAG (https://en.wikipedia.org/wiki/Retrieval-augmented_generation).

This is a fork from https://github.com/vitali87/code-graph-rag/tree/main we used during our AI Week. We forked initially because we wanted to add support for Claude/Anthropic and add class attributes to the graph nodes that represent classes.

We used this as an MCP server accessible to Claude Code. We populated it with the API codebase (scanning a codebase is out of the box behaviour). Then we extended the graph by adding the database schema
Finally, we used Claude Code to link the Database tables to the "Model" (DTO) classes in the API code.

This graph showed value when asking design questions such as "which classes are modifying points calculation data ?". The graph is only a static view of references. The graph only shows what function refers to what other functions, not when they are being invoked. So dynamic behaviour (e.g. sequence diagrams) cannot be directly queried without access to the codebase as well.

## How to Run
