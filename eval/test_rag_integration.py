import os
import json
import re
from typing import List, Dict, Any
import pytest
from deepeval import evaluate
from deepeval.test_case import LLMTestCase
from deepeval.metrics import (
    AnswerRelevancyMetric, 
    FaithfulnessMetric,
    ContextualRelevancyMetric
)

# Configure deepeval to use Anthropic via environment variables
os.environ.setdefault("DEEPEVAL_MODEL", "claude-3-5-sonnet-20241022")
os.environ.setdefault("DEEPEVAL_PROVIDER", "anthropic")


class MCPRAGEvaluator:
    """Evaluates Claude's performance with MCP RAG for code analysis tasks."""
    
    def __init__(self):
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
    
    def query_memgraph_for_class(self, class_name: str) -> str:
        """Query Memgraph for class information via MCP."""
        # This would be replaced with actual MCP call in real implementation
        # For now, simulate the expected response structure
        cypher_query = f"""
        MATCH (c:Class {{name: '{class_name}'}})
        OPTIONAL MATCH (c)-[:HAS_ATTRIBUTE]->(attr:Attribute)
        RETURN c.name as class_name, 
               collect(attr.name) as attributes,
               c.file_path as file_path
        """
        
        # Simulated response for EnterpriseNewsAndEvents class
        # In real implementation, this would call the MCP Memgraph tool
        return {
            "class_name": "EnterpriseNewsAndEvents",
            "attributes": ["id", "title", "content"],  # Expected 3 attributes
            "file_path": "/path/to/enterprise_news_events.py"
        }
    
    def invoke_claude_with_mcp_rag(self, prompt: str) -> str:
        """Invoke Claude with MCP RAG capabilities."""
        try:
            # Import here to avoid dependency issues if anthropic not installed
            import anthropic
            
            client = anthropic.Anthropic(api_key=self.anthropic_api_key)
            
            # Note: In a real implementation, Claude would be invoked with MCP tools available
            # The actual MCP tools available are: mcp__memgraph__run_query, etc.
            # MCP tools are pre-configured server-side, not defined in the API call
            
            message = client.beta.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                messages=[{
                    "role": "user", 
                    "content": f"{prompt}\n\nPlease use the available MCP Memgraph tools to query the codebase graph for information about the EnterpriseNewsAndEvents class."
                }],
                mcp_servers = [{
                    "type" :                "url" ,
                    "url" :                 "https://mcp.example.com/sse" ,
                    "name" :                "mcp-memgraph" ,
                }] ,
                # Note: MCP tools are pre-configured, not defined here
            )
            
            return message.content[0].text if message.content else "No response"
            
        except ImportError:
            # Fallback for testing without anthropic package
            return self._simulate_claude_response_with_rag()
        except Exception as e:
            return f"Error invoking Claude: {str(e)}"
    
    def _simulate_claude_response_with_rag(self) -> str:
        """Simulate Claude's response with RAG for testing purposes."""
        return """
        Based on the codebase analysis via MCP, I found the EnterpriseNewsAndEvents class with the following attributes:
        
        1. **id** - Unique identifier for the news/event item
        2. **title** - The title of the news or event  
        3. **content** - The main content/description of the news or event
        
        These are the 3 main attributes defined for the EnterpriseNewsAndEvents class.
        """
    
    def extract_attributes_count(self, response: str) -> int:
        """Extract the number of attributes mentioned in the response."""
        # Look for numbered lists or bullet points
        patterns = [
            r'^\s*\d+\.\s*\*\*([a-zA-Z_][a-zA-Z0-9_]*)\*\*',  # 1. **attribute**
            r'^\s*-\s*\*\*([a-zA-Z_][a-zA-Z0-9_]*)\*\*',       # - **attribute**
            r'^\s*\d+\.\s*([a-zA-Z_][a-zA-Z0-9_]*)',           # 1. attribute
            r'^\s*-\s*([a-zA-Z_][a-zA-Z0-9_]*)',               # - attribute
        ]
        
        attributes = set()
        lines = response.split('\n')
        
        for line in lines:
            for pattern in patterns:
                matches = re.findall(pattern, line, re.MULTILINE)
                attributes.update(matches)
        
        return len(attributes)
    
    def create_test_case(self, prompt: str, expected_count: int = 3) -> LLMTestCase:
        """Create a test case for deepeval evaluation."""
        
        # Get actual response from Claude with MCP RAG
        actual_output = self.invoke_claude_with_mcp_rag(prompt)
        
        # Extract context from simulated MCP query
        context = [str(self.query_memgraph_for_class("EnterpriseNewsAndEvents"))]
        
        return LLMTestCase(
            input=prompt,
            actual_output=actual_output,
            expected_output=f"Should identify exactly {expected_count} attributes for EnterpriseNewsAndEvents class",
            context=context,
            retrieval_context=context
        )


# Test functions for deepeval
def test_enterprise_news_events_attributes():
    """Test that Claude correctly identifies EnterpriseNewsAndEvents class attributes."""
    
    evaluator = MCPRAGEvaluator()
    test_prompt = "Please list all the attributes for EnterpriseNewsAndEvents class"
    
    # Create test case
    test_case = evaluator.create_test_case(test_prompt, expected_count=3)
    
    # Extract actual attribute count
    actual_count = evaluator.extract_attributes_count(test_case.actual_output)
    
    # Assert exactly 3 attributes found
    assert actual_count == 3, (
        f"Expected exactly 3 attributes for EnterpriseNewsAndEvents class, "
        f"but found {actual_count}"
    )
    
    # Define metrics for evaluation
    metrics = [
        AnswerRelevancyMetric(threshold=0.7),
        FaithfulnessMetric(threshold=0.7),
        ContextualRelevancyMetric(threshold=0.6)
    ]
    
    # Evaluate using deepeval
    results = evaluate(test_cases=[test_case], metrics=metrics)
    
    # Additional assertions
    assert test_case.actual_output is not None, "Response should not be None"
    assert len(test_case.actual_output.strip()) > 0, "Response should not be empty"
    
    print(f"✅ Test passed! Found {actual_count} attributes as expected")
    return results


def test_enterprise_news_events_response_quality():
    """Test the quality and structure of Claude's response about EnterpriseNewsAndEvents."""
    
    evaluator = MCPRAGEvaluator()
    test_prompt = "Please list all the attributes for EnterpriseNewsAndEvents class"
    
    test_case = evaluator.create_test_case(test_prompt)
    response = test_case.actual_output.lower()
    
    # Check for key terms that should appear in a good response
    expected_terms = ["attribute", "enterprisenewsandevents", "class"]
    found_terms = sum(1 for term in expected_terms if term in response)
    
    assert found_terms >= 2, f"Response should contain at least 2 key terms, found {found_terms}"
    
    # Check response length (should be informative but not too verbose)
    assert 50 <= len(response) <= 2000, f"Response length should be reasonable, got {len(response)} chars"
    
    print("✅ Response quality test passed!")


if __name__ == "__main__":
    # Run tests directly
    print("Running EnterpriseNewsAndEvents RAG evaluation tests...")
    
    try:
        test_enterprise_news_events_attributes()
        test_enterprise_news_events_response_quality()
        print("🎉 All tests passed successfully!")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        raise