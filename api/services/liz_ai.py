"""
Liz AI Service - OpenAI Integration for YouTube Contextual Product Pipeline.
Handles all interactions with OpenAI's GPT-4o model for keyword generation and analysis.
"""
from openai import OpenAI
from api.config import settings
import json
from typing import Dict, List, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LANGUAGE_LABELS = {
    "en": "English",
    "es": "Spanish",
    "pt": "Portuguese",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "hi": "Hindi",
    "ar": "Arabic",
}

MARKET_LABELS = {
    "US": "United States",
    "MX": "Mexico",
    "CO": "Colombia",
    "AR": "Argentina",
    "CL": "Chile",
    "BR": "Brazil",
    "ES": "Spain",
    "GB": "United Kingdom",
    "FR": "France",
    "DE": "Germany",
    "IT": "Italy",
    "CA": "Canada",
    "AU": "Australia",
    "JP": "Japan",
    "KR": "South Korea",
    "SG": "Singapore",
    "AE": "United Arab Emirates",
    "NL": "Netherlands",
    "BE": "Belgium",
    "SE": "Sweden",
    "NO": "Norway",
    "DK": "Denmark",
    "IE": "Ireland",
    "NZ": "New Zealand",
}


class LizAIService:
    """
    Service class for interacting with OpenAI's API (Liz AI).
    Provides methods for campaign analysis and keyword generation.
    """
    
    def __init__(self):
        """Initialize OpenAI client with API key from settings."""
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.temperature = settings.openai_temperature
        self.max_tokens = settings.openai_max_tokens
    
    def generate_keywords(
        self,
        campaign_data: Dict[str, Any],
        num_core: int = 10,
        num_long_tail: int = 15,
        num_related: int = 10,
        num_intent_based: int = 10
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Generate keywords for a campaign using OpenAI's GPT-4o.
        
        Args:
            campaign_data: Dictionary containing campaign information
                - name: Campaign name
                - brand_name: Brand name
                - product_category: Product category
                - campaign_goal: Campaign objective
                - campaign_definition: Detailed description
                - brand_context_text: Brand guidelines (optional)
            num_core: Number of core keywords to generate (default: 10)
            num_long_tail: Number of long-tail keywords to generate (default: 15)
            num_related: Number of related keywords to generate (default: 10)
            num_intent_based: Number of intent-based keywords to generate (default: 10)
        
        Returns:
            Dictionary with four keyword categories, each containing a list of keywords
            with their text and relevance score (0-1)
        
        Raises:
            Exception: If OpenAI API call fails
        """
        try:
            # Build system prompt
            system_prompt = self._build_system_prompt()
            
            # Build user prompt with campaign context
            user_prompt = self._build_keyword_generation_prompt(
                campaign_data,
                num_core,
                num_long_tail,
                num_related,
                num_intent_based
            )
            
            logger.info(f"Generating keywords for campaign: {campaign_data.get('name')}")
            
            # Call OpenAI API with JSON mode
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"}
            )
            
            # Extract and parse JSON response
            content = response.choices[0].message.content
            keywords_data = json.loads(content)
            
            # Log token usage
            logger.info(f"Token usage - Prompt: {response.usage.prompt_tokens}, "
                       f"Completion: {response.usage.completion_tokens}, "
                       f"Total: {response.usage.total_tokens}")
            
            return keywords_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenAI response as JSON: {e}")
            raise Exception("Invalid JSON response from AI service")
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise Exception(f"Failed to generate keywords: {str(e)}")
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt for keyword generation."""
        return """You are Liz AI, an expert keyword strategist for YouTube programmatic video campaigns.

Your role is to generate high-quality, targeted keywords that will help discover relevant YouTube videos for programmatic ad placement.

Always follow the user's locale instructions. When a primary language or market is provided, generate keywords in that language and favor terminology familiar to audiences in that market.

You must generate four categories of keywords:

1. **Core Keywords** (5-20 keywords): Fundamental, high-volume terms directly related to the campaign topic
   - Should be 1-3 words
   - Highly relevant to the product/service
   - Example: "smartphone", "tech review", "mobile phone"

2. **Long-Tail Keywords** (10-30 keywords): Specific, lower-volume phrases with higher intent
   - Should be 3-6 words
   - More specific and targeted
   - Example: "best budget smartphone 2024", "flagship phone camera test"

3. **Related Topics** (5-20 keywords): Adjacent topics and themes
   - Connected but not directly about the product
   - Helps expand reach to relevant audiences
   - Example: "mobile gaming", "phone accessories", "tech unboxing"

4. **Intent-Based Keywords** (5-20 keywords): Keywords that capture user intent
   - Focus on what users want to do or learn
   - Include modifiers like "how to", "best", "review", "comparison"
   - Example: "how to choose a smartphone", "best phones for photography"

For each keyword, assign a relevance_score (0.0 to 1.0) based on:
- Relevance to campaign goal (40%)
- Alignment with brand/product (30%)
- Search volume potential (20%)
- Targeting precision (10%)

Respond ONLY with valid JSON in this exact format:
{
  "core_keywords": [
    {"keyword": "keyword text", "relevance_score": 0.95},
    ...
  ],
  "long_tail_keywords": [
    {"keyword": "keyword text", "relevance_score": 0.85},
    ...
  ],
  "related_topics": [
    {"keyword": "keyword text", "relevance_score": 0.75},
    ...
  ],
  "intent_based_keywords": [
    {"keyword": "keyword text", "relevance_score": 0.80},
    ...
  ]
}"""
    
    def _build_keyword_generation_prompt(
        self,
        campaign_data: Dict[str, Any],
        num_core: int,
        num_long_tail: int,
        num_related: int,
        num_intent_based: int
    ) -> str:
        """Build the user prompt with campaign context."""
        language_code = (campaign_data.get("primary_language") or "en").lower()
        market_code = (campaign_data.get("primary_market") or "US").upper()
        language_label = LANGUAGE_LABELS.get(language_code, language_code)
        market_label = MARKET_LABELS.get(market_code, market_code)

        prompt = f"""Generate keywords for this programmatic video campaign:

**Campaign Name:** {campaign_data.get('name')}
**Brand:** {campaign_data.get('brand_name')}
**Product Category:** {campaign_data.get('product_category')}
**Campaign Goal:** {campaign_data.get('campaign_goal')}
**Primary Language:** {language_label} ({language_code.upper()})
**Primary Market:** {market_label} ({market_code})

**Campaign Description:**
{campaign_data.get('campaign_definition')}
"""
        
        # Add brand context if provided
        if campaign_data.get('brand_context_text'):
            prompt += f"""
**Brand Context & Guidelines:**
{campaign_data.get('brand_context_text')}
"""
        
        prompt += f"""
**Requirements:**
- Generate exactly {num_core} core keywords
- Generate exactly {num_long_tail} long-tail keywords
- Generate exactly {num_related} related topic keywords
- Generate exactly {num_intent_based} intent-based keywords
- Each keyword must have a relevance_score between 0.0 and 1.0
- Keywords should be optimized for YouTube video discovery
- Consider YouTube search patterns and video content themes
- Ensure diversity within each category
- All keywords must be written in {language_label} ({language_code.upper()}) with correct accents and casing.
- Prioritize terminology and search behaviour common in {market_label} ({market_code}).

Respond with JSON only, no additional text."""
        
        return prompt


# Global instance
liz_ai_service = LizAIService()
