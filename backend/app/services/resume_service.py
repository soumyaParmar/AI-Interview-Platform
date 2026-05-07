import io
import json
from pypdf import PdfReader
from ..core import agents

class ResumeService:
    @staticmethod
    def extract_text_from_pdf(file_bytes: bytes) -> str:
        """
        Extracts raw text from a PDF file using pypdf.
        """
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            print(f"Error extracting PDF: {e}")
            return ""

    async def parse_resume_with_ai(self, resume_text: str):
        """
        Uses an AI chain to extract structured details from raw resume text.
        """
        if not resume_text.strip():
            return {}
            
        chain = agents.get_resume_extraction_chain()
        result = await chain.ainvoke({"resume_text": resume_text})
        
        # Parse JSON results
        return self._parse_json(result.content)

    def _parse_json(self, text: str):
        import re
        json_match = re.search(r"(\{.*\})", text, re.DOTALL)
        clean_json = json_match.group(1) if json_match else text
        try:
            return json.loads(clean_json)
        except:
            return {"raw": text}
