import ollama
import json
import re
from loguru import logger

class SemanticAnalyzer:
    def __init__(self, model="llama3.2:3b", prompt_template_path="config/semantic_prompt.txt"):
        self.model = model
        with open(prompt_template_path, "r") as f:
            self.prompt_template = f.read()
            
        # Fast regex for common French radio transition phrases
        self.regex_patterns = [
            r"c'est l'heure de",
            r"on retrouve",
            r"la chronique de",
            r"bonjour à tous",
            r"notre invité",
            r"tout de suite",
            r"bienvenue dans"
        ]

    def fast_check(self, text):
        """Quickly check for keywords."""
        for pattern in self.regex_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def analyze(self, text):
        """
        Ask LLM to analyze the text for chronicle start.
        """
        if not text.strip():
            return {"is_transition": False, "confidence": 0.0}

        # If it doesn't pass fast check AND text is short, maybe skip? 
        # Actually let's always call LLM if there's enough text, but use regex as a boost.
        
        prompt = self.prompt_template.format(text=text)
        
        try:
            response = ollama.generate(model=self.model, prompt=prompt, format="json")
            result = json.loads(response['response'])
            
            # Boost confidence if regex matched
            if self.fast_check(text):
                result['confidence'] = min(1.0, result.get('confidence', 0) + 0.2)
                
            logger.debug(f"LLM Analysis: {result}")
            return result
        except Exception as e:
            logger.error(f"LLM Error: {e}")
            return {"is_transition": False, "confidence": 0.0, "reason": str(e)}
