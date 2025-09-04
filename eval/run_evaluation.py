#!/usr/bin/env python3
"""
Script to run the EnterpriseNewsAndEvents RAG evaluation using deepeval.
"""

import os
import sys
from pathlib import Path

# Add the parent directory to Python path to import codebase_rag
sys.path.append(str(Path(__file__).parent.parent))

try:
    from test_rag_integration import test_enterprise_news_events_attributes, test_enterprise_news_events_response_quality
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure deepeval and anthropic are installed:")
    print("pip install -r requirements.txt")
    sys.exit(1)


def main():
    """Run the evaluation tests."""
    print("🚀 Starting EnterpriseNewsAndEvents RAG Evaluation")
    print("=" * 50)
    
    # Check for required environment variables
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️  Warning: ANTHROPIC_API_KEY not found in environment")
        print("   The test will use simulated responses for demonstration")
    
    try:
        # Run the main test
        print("\n🔍 Testing attribute detection...")
        test_enterprise_news_events_attributes()
        
        print("\n📊 Testing response quality...")
        test_enterprise_news_events_response_quality()
        
        print("\n" + "=" * 50)
        print("🎉 All evaluation tests completed successfully!")
        print("\nTest Results Summary:")
        print("✅ Attribute count assertion: PASSED")
        print("✅ Response quality check: PASSED") 
        print("✅ deepeval metrics: EVALUATED")
        
    except Exception as e:
        print(f"\n❌ Evaluation failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)