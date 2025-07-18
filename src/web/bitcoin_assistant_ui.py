#!/usr/bin/env python3
"""
Bitcoin Knowledge Assistant Web UI using Gradio
"""

import os
import sys
import gradio as gr
import requests
import json
from typing import List, Tuple

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Configuration
API_BASE_URL = "http://localhost:8000"

def query_bitcoin_assistant(question: str) -> Tuple[str, str]:
    """Query the Bitcoin Assistant API"""
    
    if not question.strip():
        return "Please enter a question about Bitcoin or blockchain technology.", ""
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/query",
            json={"question": question},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            answer = data.get('answer', 'No answer received')
            
            # Format sources
            sources = data.get('sources', [])
            sources_text = ""
            if sources:
                sources_text = "**Sources:**\n"
                for i, source in enumerate(sources[:5], 1):
                    sources_text += f"{i}. {source.get('name', 'Unknown')}\n"
            
            return answer, sources_text
        else:
            error_msg = f"API Error ({response.status_code}): {response.text}"
            return error_msg, ""
            
    except requests.exceptions.ConnectionError:
        return "❌ Cannot connect to Bitcoin Assistant API. Make sure the FastAPI server is running on port 8000.", ""
    except Exception as e:
        return f"❌ Error: {str(e)}", ""

def get_available_sources() -> str:
    """Get list of available sources"""
    try:
        response = requests.get(f"{API_BASE_URL}/sources", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            sources = data.get('available_sources', [])
            total = data.get('total_sources', 0)
            
            if sources:
                sources_list = "\n".join([f"• {source}" for source in sources])
                return f"**Available Sources ({total} total):**\n\n{sources_list}"
            else:
                return "No sources found in the knowledge base."
        else:
            return f"Error fetching sources: {response.text}"
            
    except Exception as e:
        return f"Error: {str(e)}"

def check_api_health() -> str:
    """Check API health status"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            status = data.get('status', 'unknown')
            pinecone_status = data.get('pinecone_assistant', 'unknown')
            server_info = data.get('server_info', {})
            
            return f"✅ **API Status:** {status}\n✅ **Pinecone Assistant:** {pinecone_status}\n📊 **Server:** {server_info.get('name', 'Unknown')} v{server_info.get('version', 'Unknown')}"
        else:
            return f"❌ **API Health Check Failed:** {response.text}"
            
    except Exception as e:
        return f"❌ **Connection Error:** {str(e)}"

# Sample questions for quick testing
SAMPLE_QUESTIONS = [
    "What is Bitcoin and how does it work?",
    "Explain the Lightning Network",
    "What are the key features of blockchain technology?",
    "Tell me about the GENIUS Act",
    "What are decentralized applications (dApps)?",
    "How does Bitcoin mining work?",
    "What is the difference between Bitcoin and traditional currency?",
    "Explain Bitcoin's proof-of-work consensus mechanism"
]

# Create Gradio interface
def create_bitcoin_assistant_ui():
    """Create the Gradio web interface"""
    
    with gr.Blocks(
        title="Bitcoin Knowledge Assistant",
        theme=gr.themes.Soft(),
        css="""
        .gradio-container {
            max-width: 1200px !important;
        }
        .question-box {
            min-height: 100px;
        }
        .answer-box {
            min-height: 200px;
        }
        """
    ) as interface:
        
        # Header
        gr.Markdown("""
        # 🪙 Bitcoin Knowledge Assistant
        
        Ask questions about Bitcoin, blockchain technology, Lightning Network, dApps, regulations, and more!
        
        Powered by **Pinecone Assistant** with intelligent document retrieval
        
        *Automatically finds the most relevant sources to answer your questions.*
        """)
        
        with gr.Row():
            with gr.Column(scale=2):
                # Main chat interface
                with gr.Group():
                    question_input = gr.Textbox(
                        label="Ask a Bitcoin Question",
                        placeholder="e.g., What is Bitcoin and how does it work?",
                        lines=3,
                        elem_classes=["question-box"]
                    )
                    
                    with gr.Row():
                        submit_btn = gr.Button("Ask Question", variant="primary", size="lg")
                        clear_btn = gr.Button("Clear", variant="secondary")
                    

                
                # Sample questions
                with gr.Group():
                    gr.Markdown("### 💡 Sample Questions")
                    sample_buttons = []
                    for i in range(0, len(SAMPLE_QUESTIONS), 2):
                        with gr.Row():
                            for j in range(2):
                                if i + j < len(SAMPLE_QUESTIONS):
                                    btn = gr.Button(
                                        SAMPLE_QUESTIONS[i + j], 
                                        size="sm",
                                        variant="outline"
                                    )
                                    sample_buttons.append((btn, SAMPLE_QUESTIONS[i + j]))
            
            with gr.Column(scale=3):
                # Answer display
                answer_output = gr.Markdown(
                    label="Answer",
                    value="Ask a question to get started!",
                    elem_classes=["answer-box"]
                )
                
                sources_output = gr.Markdown(
                    label="Sources",
                    value=""
                )
        
        # Status and info section
        with gr.Row():
            with gr.Column():
                with gr.Group():
                    gr.Markdown("### 🔧 System Status")
                    status_output = gr.Markdown("Click 'Check Status' to verify API connection")
                    status_btn = gr.Button("Check Status", size="sm")
            
            with gr.Column():
                with gr.Group():
                    gr.Markdown("### 📚 Knowledge Base")
                    sources_list_output = gr.Markdown("Click 'List Sources' to see available documents")
                    sources_btn = gr.Button("List Sources", size="sm")
        
        # Event handlers
        def submit_question(question):
            if not question.strip():
                return "Please enter a question.", ""
            return query_bitcoin_assistant(question)
        
        def set_sample_question(sample_q):
            return sample_q
        
        # Wire up the interface
        submit_btn.click(
            fn=submit_question,
            inputs=[question_input],
            outputs=[answer_output, sources_output]
        )
        
        question_input.submit(
            fn=submit_question,
            inputs=[question_input],
            outputs=[answer_output, sources_output]
        )
        
        clear_btn.click(
            fn=lambda: ("", "Ask a question to get started!", ""),
            outputs=[question_input, answer_output, sources_output]
        )
        
        status_btn.click(
            fn=check_api_health,
            outputs=status_output
        )
        
        sources_btn.click(
            fn=get_available_sources,
            outputs=sources_list_output
        )
        
        # Wire up sample question buttons
        for btn, sample_q in sample_buttons:
            btn.click(
                fn=set_sample_question,
                inputs=gr.State(sample_q),
                outputs=question_input
            )
    
    return interface

if __name__ == "__main__":
    # Create and launch the interface
    interface = create_bitcoin_assistant_ui()
    
    print("🚀 Starting Bitcoin Knowledge Assistant Web UI...")
    print("📡 Make sure the FastAPI server is running on http://localhost:8000")
    print("🌐 Gradio UI will be available at http://localhost:7860")
    
    # Get port from environment or use default
    ui_port = int(os.getenv('GRADIO_SERVER_PORT', os.getenv('UI_PORT', 7860)))
    ui_host = os.getenv('GRADIO_SERVER_NAME', os.getenv('UI_HOST', '0.0.0.0'))
    
    interface.launch(
        server_name=ui_host,
        server_port=ui_port,
        share=False,
        show_error=True
    )