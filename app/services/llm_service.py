import os
from typing import List, Dict
import openai
from anthropic import Anthropic
import google.generativeai as genai
import time

# Pricing per 1M tokens
# Documentation:
# - OpenAI: https://openai.com/api/pricing/
# - Anthropic: https://www.anthropic.com/pricing#api
# - Google: https://ai.google.dev/gemini-api/docs/pricing
PRICING = {
    # OpenAI Models
    'gpt-4.1': {'input': 2.0, 'output': 8.0},
    'gpt-4.1-mini': {'input': 0.40, 'output': 1.60},
    'gpt-4.1-nano': {'input': 0.1, 'output': 0.4},
    'gpt-4o-mini': {'input': 0.15, 'output': 0.6},
    # 'o3': {'input': 10.0, 'output': 40.0},  # Disabled: Requires organization verification at https://platform.openai.com/settings/organization/general
    'o4-mini': {'input': 1.1, 'output': 4.4},
    
    # Anthropic Models
    'claude-3-5-haiku-latest': {'input': 0.8, 'output': 4.0},
    'claude-3-7-sonnet-latest': {'input': 3.0, 'output': 15.0},
    'claude-sonnet-4-20250514': {'input': 3.0, 'output': 15.0},
    'claude-opus-4-20250514': {'input': 15.0, 'output': 75.0},
    
    # Google Models
    'gemini-2.5-flash-preview-05-20': {'input': 0.15, 'output': 0.6},
    'gemini-2.5-pro-preview-06-05': {'input': 1.25, 'output': 10.0},
    'gemini-2.0-flash': {'input': 0.1, 'output': 0.4},
    'gemini-1.5-flash': {'input': 0.075, 'output': 0.3},
    'gemini-1.5-pro': {'input': 1.25, 'output': 5.0}
}

# Maximum output tokens for a 10-cent cost limit, capped at 16384
MAX_OUTPUT_TOKENS = {
    # OpenAI Models
    'gpt-4.1': min(12500, 16384),
    'gpt-4.1-mini': min(62500, 16384),
    'gpt-4.1-nano': min(250000, 16384),
    'gpt-4o-mini': min(166667, 16384),
    # 'o3': min(250000, 16384),  # Disabled: Requires organization verification at https://platform.openai.com/settings/organization/general
    'o4-mini': min(22727, 16384),
    
    # Anthropic Models
    'claude-3-5-haiku-latest': min(25000, 8192),  # Claude 3.5 Haiku has a max of 8192
    'claude-3-7-sonnet-latest': min(6667, 16384),
    'claude-sonnet-4-20250514': min(6667, 16384),
    'claude-opus-4-20250514': min(1333, 16384),
    
    # Google Models
    'gemini-2.5-flash-preview-05-20': min(166667, 16384),
    'gemini-2.5-pro-preview-06-05': min(10000, 16384),
    'gemini-2.0-flash': min(250000, 16384),
    'gemini-1.5-flash': min(333333, 16384),
    'gemini-1.5-pro': min(20000, 16384)
}

__all__ = ['LLMService', 'PRICING', 'MODEL_MAPPINGS', 'MAX_OUTPUT_TOKENS']

# Model display names and their corresponding API model names
MODEL_MAPPINGS = {
    # OpenAI Models
    'GPT-4.1': 'gpt-4.1',
    'GPT-4.1 Mini': 'gpt-4.1-mini',
    'GPT-4.1 Nano': 'gpt-4.1-nano',
    'GPT-4o Mini': 'gpt-4o-mini',
    # 'O3': 'o3',  # Disabled: Requires organization verification at https://platform.openai.com/settings/organization/general
    'O4 Mini': 'o4-mini',
    
    # Anthropic Models
    'Claude 3.5 Haiku': 'claude-3-5-haiku-latest',
    'Claude 3.7 Sonnet': 'claude-3-7-sonnet-latest',
    'Claude Sonnet 4': 'claude-sonnet-4-20250514',
    'Claude Opus 4': 'claude-opus-4-20250514',
    
    # Google Models
    'Gemini 2.5 Flash': 'gemini-2.5-flash-preview-05-20',
    'Gemini 2.5 Pro': 'gemini-2.5-pro-preview-06-05',
    'Gemini 2.0 Flash': 'gemini-2.0-flash',
    'Gemini 1.5 Flash': 'gemini-1.5-flash',
    'Gemini 1.5 Pro': 'gemini-1.5-pro'
}

class LLMService:
    def __init__(self):
        # Initialize OpenAI
        self.openai_client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Initialize Anthropic
        self.anthropic = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        
        # Initialize Google Gemini
        genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
        self.gemini_models = {}
        for model_name in [m for m in MODEL_MAPPINGS.values() if m.startswith('gemini')]:
            try:
                self.gemini_models[model_name] = genai.GenerativeModel(model_name)
            except Exception as e:
                print(f"Error initializing Gemini model '{model_name}': {e}")

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
                responses.append({
                    'llm_name': display_name,
                    'content': f"Error: {str(e)}",
                    'metadata': {
                        'input_tokens': 0,
                        'output_tokens': 0,
                        'total_tokens': 0,
                        'cost': 0.0,
                        'model': model_name,
                        'error': str(e)
                    }
                })

        return responses

    def _get_gpt4_response(self, question: str, model_name: str) -> Dict:
        """Get response from OpenAI model."""
        max_tokens = MAX_OUTPUT_TOKENS.get(model_name, 1000)  # Default to 1000 if not found
        
        start_time = time.time()
        
        # Use different parameter name for O4-mini model
        if model_name == 'o4-mini':
            response = self.openai_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful AI assistant."},
                    {"role": "user", "content": question}
                ],
                max_completion_tokens=max_tokens
            )
        else:
            response = self.openai_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful AI assistant."},
                    {"role": "user", "content": question}
                ],
                max_tokens=max_tokens
            )
        
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
        
        response = self.anthropic.messages.create(
            model=model_name,
            max_tokens=max_tokens,
            messages=[
                {"role": "user", "content": question}
            ]
        )
        
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
        if model_name not in self.gemini_models:
            raise Exception(f"Gemini model '{model_name}' is not available.")
        
        max_tokens = MAX_OUTPUT_TOKENS.get(model_name, 1000)  # Default to 1000 if not found
        
        start_time = time.time()
        
        response = self.gemini_models[model_name].generate_content(
            question,
            generation_config={"max_output_tokens": max_tokens}
        )
        
        response_time = time.time() - start_time
        
        token_count = getattr(response, 'token_count', 0)
        
        # For Gemini, we'll estimate input/output tokens as 50/50 split
        input_tokens = token_count // 2
        output_tokens = token_count - input_tokens
        
        # Calculate costs
        pricing = PRICING.get(model_name, {})
        input_cost = (input_tokens / 1_000_000) * pricing.get('input', 0)
        output_cost = (output_tokens / 1_000_000) * pricing.get('output', 0)
        
        return {
            'content': response.text,
            'metadata': {
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'total_tokens': token_count,
                'input_cost': input_cost,
                'output_cost': output_cost,
                'model': model_name,
                'safety_ratings': getattr(response, 'safety_ratings', None),
                'response_time': response_time
            }
        }

    def generate_summary(self, question: str, responses: List[Dict]) -> Dict:
        """Generate a summary of the responses using Gemini 2.5 Flash."""
        # Format the responses for the prompt
        formatted_responses = []
        for resp in responses:
            formatted_responses.append(f"Response from {resp['llm_name']}:\n{resp['content']}\n")
        
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

        # Get the summary using Gemini 2.5 Flash
        model_name = 'gemini-2.5-flash-preview-05-20'
        response = self._get_gemini_response(prompt, model_name)
        
        return {
            'llm_name': 'Gemini 2.5 Flash',
            'content': response['content'],
            'metadata': response['metadata']
        } 