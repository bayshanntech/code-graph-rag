# RAG Evaluation with deepeval

This directory contains end-to-end evaluation tests for the RAG system using deepeval to test Claude's performance with MCP integration.

## Test Overview

The main test evaluates Claude's ability to correctly identify attributes of the `EnterpriseNewsAndEvents` class using the RAG system exposed via MCP (Model Context Protocol).

### Test Assertion
- **Expected Result**: Exactly 3 attributes should be identified for the `EnterpriseNewsAndEvents` class
- **Evaluation Metrics**: Answer relevancy, faithfulness, and contextual relevancy

## Files

- `test_rag_integration.py` - Main evaluation test with deepeval integration
- `test_enterprise_news_events.py` - Alternative test implementation  
- `run_evaluation.py` - Script to execute the evaluation tests
- `requirements.txt` - Dependencies needed for evaluation
- `deepeval_config.yaml` - Configuration for deepeval framework

## Setup

1. Install dependencies:
```bash
pip install -r eval/requirements.txt
```

2. Set environment variable:
```bash
export ANTHROPIC_API_KEY="your_api_key_here"
```

## Running Tests

### Option 1: Run via deepeval CLI
```bash
cd eval
deepeval test run test_rag_integration.py
```

### Option 2: Run the evaluation script
```bash
cd eval  
python run_evaluation.py
```

### Option 3: Run individual test
```bash
cd eval
python test_rag_integration.py
```

## Test Details

The test performs the following steps:

1. **Invoke Claude** with the prompt: "Please list all the attributes for EnterpriseNewsAndEvents class"
2. **MCP Integration** - Claude uses the MCP Memgraph tool to query the codebase knowledge graph
3. **Response Analysis** - Extract and count attributes from Claude's response
4. **Assertions**:
   - Exactly 3 attributes are identified
   - Response quality meets deepeval metrics thresholds
   - Response contains expected terminology

## Expected Output

When successful, the test should output:
```
✅ Test passed! Found 3 attributes as expected
✅ Response quality test passed!
🎉 All evaluation tests completed successfully!
```

## Troubleshooting

- Ensure `ANTHROPIC_API_KEY` is set in your environment
- Verify MCP server is running and accessible
- Check that the `EnterpriseNewsAndEvents` class exists in your codebase
- Install all dependencies from `requirements.txt`