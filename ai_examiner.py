import os
import threading

# We import Anthropic dynamically or lazily if we want to avoid crashing if it's not installed,
# but the prompt implies we just use the anthropic SDK.
try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

class AIExaminer:
    def __init__(self):
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            print("Notice: ANTHROPIC_API_KEY not set. AI Examiner disabled.")
        elif Anthropic is None:
            print("Notice: 'anthropic' package not installed. AI Examiner disabled.")
            
        self.current_question = None
        self._is_generating = False

    def generate_question_async(self, reaction_record):
        if not self.api_key or Anthropic is None:
            self.current_question = "AI Examiner disabled (Missing API Key or anthropic pkg)."
            return
            
        if self._is_generating:
            return
            
        self._is_generating = True
        self.current_question = "Generating question..."
        
        # Run in thread so we don't block the OpenCV frame loop
        threading.Thread(target=self._generate, args=(reaction_record,), daemon=True).start()
        
    def _generate(self, r):
        try:
            client = Anthropic(api_key=self.api_key)
            
            system_prompt = (
                "You are a strict chemistry examiner. Generate ONE short, Socratic question "
                "about the specific reaction provided in the context. "
                "CRITICAL: Ask ONLY about this reaction's chemistry (reactants, products, conditions, observations). "
                "DO NOT introduce facts or concepts beyond what is explicitly given in the record. "
                "Keep the question to 1-2 sentences maximum."
            )
            
            prompt = (
                f"Reaction Context:\\n"
                f"- Reactants: {r.get('reactant_1')} + {r.get('reactant_2')}\\n"
                f"- Conditions: {r.get('conditions')}\\n"
                f"- Products: {r.get('products')}\\n"
                f"- Equation: {r.get('equation')}\\n"
                f"- Observation: {r.get('observation')}\\n\\n"
                f"Generate a question."
            )
            
            response = client.messages.create(
                model="claude-sonnet-4-6", # User requested model string
                max_tokens=150,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            self.current_question = response.content[0].text.strip()
        except Exception as e:
            print(f"AI Examiner error: {e}")
            self.current_question = f"AI Examiner error: {e}"
        finally:
            self._is_generating = False
