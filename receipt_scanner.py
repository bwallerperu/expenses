
import os
import sys
import json
import cv2
import numpy as np
from PIL import Image
import vertexai
from vertexai.generative_models import GenerativeModel, Part, Image as VertexImage

# Configuration
PROJECT_ID = "surfn-peru"  # Using existing project ID
LOCATION = "us-central1"   # Default location
# User requested "Gemini 2.5 Flash". As of now, the latest Flash model in preview is 2.0.
# We will use 'gemini-2.0-flash-exp' to honor the "latest/2.5" request as closely as possible.
MODEL_ID = "gemini-2.5-flash" 

# Initialize Vertex AI
# This will automatically pick up Application Default Credentials (ADC)
# from the environment (e.g., GOOGLE_APPLICATION_CREDENTIALS, gcloud auth, or metadata server)
try:
    vertexai.init(project=PROJECT_ID, location=LOCATION)
except Exception as e:
    print(f"Error initializing Vertex AI: {e}")
    sys.exit(1)

def preprocess_image(image_path):
    """
    Loads an image, finds the document contour, chops off the background,
    and returns the processed image (as a PIL Image).
    """
    print(f"Processing image: {image_path}")
    
    # Load image
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not load image at {image_path}")

    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Blur to remove noise
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Edge detection
    edged = cv2.Canny(blurred, 75, 200)
    
    # Find contours
    contours, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Sort contours by area, keeping the largest one
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    
    receipt_contour = None
    
    # Loop over contours to find the document
    for c in contours:
        # Approximate the contour
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        
        # If our approximated contour has 4 points, we assume it's the document
        if len(approx) == 4:
            receipt_contour = approx
            break

    # If no 4-point contour found, just use the largest bounding box
    if receipt_contour is None and len(contours) > 0:
        x, y, w, h = cv2.boundingRect(contours[0])
        cropped = img[y:y+h, x:x+w]
        print("No 4-point contour found, using largest bounding box.")
        
    elif receipt_contour is not None:
        # 4-point transform logic could be added here for perspective correction
        # For now, let's just do a bounding rect crop of the contour to keep it simple and robust
        x, y, w, h = cv2.boundingRect(receipt_contour)
        cropped = img[y:y+h, x:x+w]
        print("Document contour found, cropping.")
    else:
        # Fallback: return original if no contours found
        print("No contours found, using original image.")
        cropped = img

    # Convert back to PIL for consistency, but Vertex AI Image can take path or bytes
    cropped_rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(cropped_rgb)
    return pil_image

def extract_data(pil_image):
    """
    Sends the image to Gemini 2.5 Flash (via Vertex AI) to extract data.
    """
    print(f"Sending to Vertex AI Model: {MODEL_ID}...")
    
    model = GenerativeModel(MODEL_ID)

    # Convert PIL image to Vertex Image
    # Using a temporary buffer to avoid saving to disk if possible, or just re-save it temporarily
    # Vertex Image.from_bytes requires bytes
    from io import BytesIO
    buffered = BytesIO()
    pil_image.save(buffered, format="JPEG")
    image_bytes = buffered.getvalue()
    vertex_image = VertexImage.from_bytes(image_bytes)

    prompt = """
    Analyze this receipt image. Extract the following information in JSON format:
    - establishment: The name of the store or merchant.
    - date: The date of the transaction (YYYY-MM-DD format).
    - amount: The total amount paid (numeric).
    
    Return ONLY valid JSON. do not include markdown blocks like ```json ... ```
    """
    
    try:
        response = model.generate_content([vertex_image, prompt])
        text_response = response.text
        
        # Clean up code blocks if present (just in case model ignores instruction)
        text_response = text_response.strip()
        if text_response.startswith('```json'):
            text_response = text_response[7:]
        if text_response.endswith('```'):
            text_response = text_response[:-3]
        
        text_response = text_response.strip()
            
        return json.loads(text_response)
        
    except Exception as e:
        print(f"Error calling Vertex AI: {e}")
        return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python receipt_scanner.py <image_path>")
        sys.exit(1)
        
    image_path = sys.argv[1]
    
    if not os.path.exists(image_path):
        print(f"File not found: {image_path}")
        sys.exit(1)

    try:
        # 1. Preprocess
        processed_image = preprocess_image(image_path)
        
        # Save processed image with _crop suffix
        base, ext = os.path.splitext(image_path)
        output_path = f"{base}_crop{ext}"
        processed_image.save(output_path)
        print(f"Processed image saved to '{output_path}'")

        # 2. Extract
        data = extract_data(processed_image)
        
        if data:
            print(json.dumps(data, indent=4))
        else:
            print("Failed to extract data.")
            
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
