from google.genai.types import GenerateContentConfig, ImageConfig
from google import genai
import base64

IMAGE_GENERATION_PROMPT = """**Role:** You are an expert educational illustrator for a K-12 online learning platform.

    **Goal:** You are to create high-quality educational illustrations that effectively convey concepts explained in tutorial videos. Your images must pair well with the narration provided.

    **Core Guidelines:**
    1. Provide illustrations that could be used as slide backgrounds in tutorial videos.
    1. Identify the core 'big idea' of each section. Prioritize a clear, symbolic representation (e.g., a lightbulb for an idea) over high-fidelity illustrations. If a concept is abstract, choose the most universally recognized icon. 
    2. When appropriate, emphasize infographics, flow diagrams, and visual metaphors to enhance understanding.
    3. Your illustrations should be clean, modern, and professional.
    4. Focus on clarity and educational value.
    5. Avoid text in images. Focus on diagrams or iconography instead.
    6. Use a consistent color palette that aligns with Code.org branding:
        - Primary: 
            - Teal: `#048899`
            - Light Teal: `#B7E0E5`
            - Dark Teal: `#026C7A`
        - Accent: 
            - Purple: `#8148B2`
            - Light Purple: `#DECEEA`
            - Dark Purple: `#603E7E`
    6. Ensure the style is suitable for an online course audience, primarily K-12 students."""

IMAGE_GEN_CONFIG = GenerateContentConfig(
                system_instruction=IMAGE_GENERATION_PROMPT,
                image_config=ImageConfig(
                    aspect_ratio="16:9"
                )
            )


GEMINI_IMG_MODEL = "gemini-2.5-flash-image"

# Helper function to generate an image for a given scene
def generate_image_for_scene(client: genai.Client, comment: str, speech: str):

    # Construct the indiuvidual prompt
    prompt = f"""Create a high-quality educational illustration for a tutorial video with this context:
    Scene context: {comment}. 
    Narration: "{speech}".
    """

    try:
        # Call the generate_content method
        response = client.models.generate_content(
            model=GEMINI_IMG_MODEL,
            contents=prompt,
            config=IMAGE_GEN_CONFIG
        )

        # Iterate through parts to find the image data
        # Note: In Python, inline_data.data is returned as bytes
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                # Convert bytes to base64 string
                base64_data = base64.b64encode(part.inline_data.data).decode('utf-8')
                return f"data:image/png;base64,{base64_data}"
        
        return None

    except Exception as e:
        print(f"Error generating image: {e}")
        raise e