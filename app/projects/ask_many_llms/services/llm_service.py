"""
Ask Many LLMs - LLM Service
Handles communication with OpenAI, Anthropic, and Google Gemini APIs
"""
import os
import logging
from typing import List, Dict
import openai
from anthropic import Anthropic
from google import genai
import time
import signal
from contextlib import contextmanager

# Set up logging
logger = logging.getLogger(__name__)

# Pricing per 1M tokens
# Documentation:
# - OpenAI: https://openai.com/api/pricing/
# - Anthropic: https://www.anthropic.com/pricing#api
# - Google: https://ai.google.dev/gemini-api/docs/pricing
PRICING = {
    # OpenAI Models
    'gpt-5.1': {'input': 1.25, 'output': 10.0},
    'gpt-5-mini': {'input': 0.25, 'output': 2.0},
    'gpt-5-nano': {'input': 0.05, 'output': 0.4},
    
    # Anthropic Models
    'claude-haiku-4-5': {'input': 1.0, 'output': 5.0},
    'claude-sonnet-4-5': {'input': 3.0, 'output': 15.0},
    'claude-opus-4-5': {'input': 5.0, 'output': 25.0},
    
    # Google Models
    'gemini-2.5-flash': {'input': 0.30, 'output': 2.50},
    'gemini-2.5-flash-lite': {'input': 0.10, 'output': 0.40},
    'gemini-2.5-pro': {'input': 1.25, 'output': 10.0}
}

# Maximum output tokens for a 10-cent cost limit, capped at 16384
MAX_OUTPUT_TOKENS = {
    # OpenAI Models
    'gpt-5.1': min(10000, 16384),
    'gpt-5-mini': min(50000, 16384),
    'gpt-5-nano': min(250000, 16384),
    
    # Anthropic Models
    'claude-haiku-4-5': min(20000, 16384),
    'claude-sonnet-4-5': min(6667, 16384),
    'claude-opus-4-5': min(4000, 16384),
    
    # Google Models
    'gemini-2.5-flash': min(40000, 16384),
    'gemini-2.5-flash-lite': min(250000, 16384),
    'gemini-2.5-pro': min(10000, 16384)
}

@contextmanager
def timeout_handler(seconds):
    """Context manager for timing out long-running operations."""
    try:
        # Try to use signal-based timeout (Unix-like systems)
        def timeout_function(signum, frame):
            raise TimeoutError(f"Operation timed out after {seconds} seconds")
        
        old_handler = signal.signal(signal.SIGALRM, timeout_function)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
    except (AttributeError, ValueError):
        # Fallback for systems that don't support SIGALRM (like Windows)
        # Just yield without timeout - gunicorn timeout will handle it
        yield

__all__ = ['LLMService', 'PRICING', 'MODEL_MAPPINGS', 'MAX_OUTPUT_TOKENS']

# Model display names and their corresponding API model names
# Ordered by price (cheapest to most expensive) within each provider
MODEL_MAPPINGS = {
    # OpenAI Models (by input price: $0.05 → $0.25 → $1.25)
    'GPT-5 Nano': 'gpt-5-nano',
    'GPT-5 Mini': 'gpt-5-mini',
    'GPT-5.1': 'gpt-5.1',
    
    # Anthropic Models (by input price: $1.00 → $3.00 → $5.00)
    'Claude Haiku 4.5': 'claude-haiku-4-5',
    'Claude Sonnet 4.5': 'claude-sonnet-4-5',
    'Claude Opus 4.5': 'claude-opus-4-5',
    
    # Google Models (by input price: $0.10 → $0.30 → $1.25)
    'Gemini 2.5 Flash Lite': 'gemini-2.5-flash-lite',
    'Gemini 2.5 Flash': 'gemini-2.5-flash',
    'Gemini 2.5 Pro': 'gemini-2.5-pro'
}

class LLMService:
    def __init__(self):
        # Initialize OpenAI
        self.openai_client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Initialize Anthropic
        self.anthropic = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        
        # Initialize Google Gemini
        self.gemini_client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))

    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate the cost of a response based on token usage."""
        if model not in PRICING:
            return 0.0
        
        pricing = PRICING[model]
        input_cost = (input_tokens / 1_000_000) * pricing['input']
        output_cost = (output_tokens / 1_000_000) * pricing['output']
        return input_cost + output_cost

    def get_responses(self, question: str, selected_models: List[str], concise: bool = False) -> List[Dict]:
        """Get responses from selected LLMs for a given question."""
        responses = []
        
        # Add concise note to question if enabled
        if concise:
            question = f"{question}\n\nPlease provide a concise and focused response without unnecessary elaboration."
        
        for display_name in selected_models:
            model_name = MODEL_MAPPINGS[display_name]
            try:
                if model_name.startswith(('gpt', 'o')):  # Handle all OpenAI models
                    response = self._get_gpt4_response(question, model_name)
                elif model_name.startswith('claude'):
                    response = self._get_claude_response(question, model_name)
                elif model_name.startswith('gemini'):
                    response = self._get_gemini_response(question, model_name)
                else:
                    continue
                
                responses.append({
                    'llm_name': display_name,
                    'content': response['content'],
                    'metadata': response['metadata']
                })
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error getting response from {display_name} ({model_name}): {error_msg}", exc_info=True)
                responses.append({
                    'llm_name': display_name,
                    'content': f"Error: {error_msg}",
                    'metadata': {
                        'input_tokens': 0,
                        'output_tokens': 0,
                        'total_tokens': 0,
                        'cost': 0.0,
                        'model': model_name,
                        'error': error_msg
                    }
                })

        return responses

    def _get_gpt4_response(self, question: str, model_name: str) -> Dict:
        """Get response from OpenAI model."""
        max_tokens = MAX_OUTPUT_TOKENS.get(model_name, 1000)  # Default to 1000 if not found
        
        start_time = time.time()
        
        try:
            with timeout_handler(90):  # 90 second timeout for OpenAI calls
                response = self.openai_client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "You are a helpful AI assistant."},
                        {"role": "user", "content": question}
                    ],
                    max_completion_tokens=max_tokens,
                    reasoning_effort="minimal"
                )
        except TimeoutError as e:
            logger.error(f"OpenAI model '{model_name}' request timed out after 90 seconds")
            raise Exception(f"OpenAI model '{model_name}' request timed out after 90 seconds")
        except Exception as e:
            logger.error(f"OpenAI API error for model '{model_name}': {str(e)}", exc_info=True)
            raise
        
        response_time = time.time() - start_time
        
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens
        
        # Calculate costs
        pricing = PRICING.get(model_name, {})
        input_cost = (input_tokens / 1_000_000) * pricing.get('input', 0)
        output_cost = (output_tokens / 1_000_000) * pricing.get('output', 0)
        
        return {
            'content': response.choices[0].message.content,
            'metadata': {
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'total_tokens': total_tokens,
                'input_cost': input_cost,
                'output_cost': output_cost,
                'model': model_name,
                'finish_reason': response.choices[0].finish_reason,
                'response_time': response_time
            }
        }

    def _get_claude_response(self, question: str, model_name: str) -> Dict:
        """Get response from Claude model."""
        max_tokens = MAX_OUTPUT_TOKENS.get(model_name, 1000)  # Default to 1000 if not found
        
        start_time = time.time()
        
        try:
            with timeout_handler(90):  # 90 second timeout for Anthropic calls
                response = self.anthropic.messages.create(
                    model=model_name,
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "user", "content": question}
                    ]
                )
        except TimeoutError as e:
            logger.error(f"Anthropic model '{model_name}' request timed out after 90 seconds")
            raise Exception(f"Anthropic model '{model_name}' request timed out after 90 seconds")
        except Exception as e:
            logger.error(f"Anthropic API error for model '{model_name}': {str(e)}", exc_info=True)
            raise
        
        response_time = time.time() - start_time
        
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        total_tokens = input_tokens + output_tokens
        
        # Calculate costs
        pricing = PRICING.get(model_name, {})
        input_cost = (input_tokens / 1_000_000) * pricing.get('input', 0)
        output_cost = (output_tokens / 1_000_000) * pricing.get('output', 0)
        
        return {
            'content': response.content[0].text,
            'metadata': {
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'total_tokens': total_tokens,
                'input_cost': input_cost,
                'output_cost': output_cost,
                'model': model_name,
                'stop_reason': response.stop_reason,
                'response_time': response_time
            }
        }

    def _get_gemini_response(self, question: str, model_name: str) -> Dict:
        """Get response from Google Gemini model."""
        max_tokens = MAX_OUTPUT_TOKENS.get(model_name, 1000)  # Default to 1000 if not found
        
        start_time = time.time()
        
        try:
            with timeout_handler(90):  # 90 second timeout for Gemini calls
                response = self.gemini_client.models.generate_content(
                    model=model_name,
                    contents=question,
                    config={"max_output_tokens": max_tokens}
                )
        except TimeoutError as e:
            logger.error(f"Gemini model '{model_name}' request timed out after 90 seconds")
            raise Exception(f"Gemini model '{model_name}' request timed out after 90 seconds")
        except Exception as e:
            logger.error(f"Gemini API error for model '{model_name}': {str(e)}", exc_info=True)
            raise
        
        response_time = time.time() - start_time
        
        # Extract token counts from Gemini response
        usage_metadata = response.usage_metadata
        if usage_metadata:
            input_tokens = usage_metadata.prompt_token_count or 0
            output_tokens = usage_metadata.candidates_token_count or 0
            total_tokens = usage_metadata.total_token_count or 0
        else:
            logger.warning(f"Gemini model '{model_name}' response has no usage_metadata")
            input_tokens = 0
            output_tokens = 0
            total_tokens = 0
        
        # Calculate costs
        pricing = PRICING.get(model_name, {})
        input_cost = (input_tokens / 1_000_000) * pricing.get('input', 0)
        output_cost = (output_tokens / 1_000_000) * pricing.get('output', 0)
        
        return {
            'content': response.text,
            'metadata': {
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'total_tokens': total_tokens,
                'input_cost': input_cost,
                'output_cost': output_cost,
                'model': model_name,
                'response_time': response_time
            }
        }

    def generate_summary(self, question: str, responses) -> Dict:
        """Generate a summary of the responses using Gemini 2.5 Flash."""
        # Format the responses for the prompt
        formatted_responses = []
        for resp in responses:
            # Handle both dict and model object
            llm_name = resp.llm_name if hasattr(resp, 'llm_name') else resp.get('llm_name')
            content = resp.content if hasattr(resp, 'content') else resp.get('content')
            formatted_responses.append(f"Response from {llm_name}:\n{content}\n")
        
        # Create the prompt
        prompt = f"""Please analyze the following responses to this question and provide a very brief summary of the key points of agreement and disagreement:

Question: {question}

Responses:
{''.join(formatted_responses)}

Please provide an extremely concise summary that:
1. Highlights only the most important points of agreement between the responses
2. Notes only major disagreements or different perspectives
3. Identifies only the most unique and valuable insights
4. Keeps the summary as brief as possible - aim for 2-3 sentences maximum

Format your response in a single, focused paragraph OR in a few bullet points."""

        # Get the summary using Gemini 2.5 Flash Lite
        model_name = 'gemini-2.5-flash-lite'
        response = self._get_gemini_response(prompt, model_name)
        
        return {
            'llm_name': 'Gemini 2.5 Flash Lite',
            'content': response['content'],
            'metadata': response['metadata']
        }

