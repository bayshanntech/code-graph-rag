# CPDValet API RAG MCP Server

## Background

This is a MPC server that runs a https://github.com/memgraph/ai-toolkit Graph Database to provide a RAG (https://en.wikipedia.org/wiki/Retrieval-augmented_generation).

This is a fork from https://github.com/vitali87/code-graph-rag/tree/main we used during our AI Week. We forked initially because we wanted to add support for Claude/Anthropic and add class attributes to the graph nodes that represent classes. The repo contains the ability to scna code and populate the graph, shcih we used. The repo also has a built-in CLI for quering the graph, which we did not use. We logged into the memgraph console however to view the graph and we used the MCP server provided here to access it from Claude Code.

We populated the graph with the API codebase initially. Then we extended the graph by adding the database schema. We created a JSON of the schema and got claude to populate the graph. (Later we added some code here to run the process directly from a DB connection, but this was not tested end-end). 
Finally, we used Claude Code to link the Database tables to the "Model" (DTO) classes in the API code.

This graph showed value when asking design questions such as "which classes are modifying points calculation data ?". The graph is only a static view of references. The graph only shows what function refers to what other functions, not when they are being invoked. So dynamic behaviour (e.g. sequence diagrams) cannot be directly queried without access to the codebase as well.


## Usage
### Initial Configuration
Create as `.env` file containing

``` 
ANTHROPIC_API_KEY={ *** your-api-key-here ***}
ANTHROPIC_ORCHESTRATOR_MODEL_ID="claude-3-5-sonnet-latest"
ANTHROPIC_CYPHER_MODEL_ID="claude-3-5-sonnet-latest"

MEMGRAPH_HOST=localhost
MEMGRAPH_PORT=7687
MEMGRAPH_HTTP_PORT=7444
LAB_PORT=3000
TARGET_REPO_PATH=.
```

### Launching Memgraph
Start the Docker desktop app (launch the daemon), then:
```
docker-compose up -d
```

### Connecting to Memgraph
1. Browse to http://localhost:3000/login
2. "Import" -> "CYPHERL File" 
3. Upload the `cpdvalet-api-db.cypherl` from this repo
4. Go to "Query execution" -> "Run.." -> "Continue.."
    - if there is no query, run `MATCH (n)-[r]->(m) RETURN n, r, m;`

You should now see a fancy graph.

### Configuring Claude Code
To allow Claude Code to use the graph via MCP, run this in a terminal (outside Claude Code):
``` 
claude mcp add-json memgraph '{"command":"uv","args":["run","--with","mcp-memgraph","--python","3.13","mcp-memgraph"]}' --scope user
```

Then launch Claude Code and verify that the mcp server is running by entering `/mcp`.

Optionally we recommend you configure a Claude Code subagent to take care of the interaction with the knowledge based, use `/agents` to set this up.

