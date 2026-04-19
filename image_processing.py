import base64
import io
import cv2
import numpy as np
import pytesseract
from PIL import Image
import re

def process_receipt_image(base64_str):
    """
    Takes a base64 encoded image, applies OpenCV contour detection to crop the receipt,
    then uses PyTesseract to find the correct text orientation and rotates the image if necessary.
    Returns a base64 encoded string of the processed image.
    """
    if "base64," in base64_str:
        header, base64_data = base64_str.split("base64,", 1)
        header += "base64,"
    else:
        header = "data:image/jpeg;base64,"
        base64_data = base64_str
        
    try:
        img_bytes = base64.b64decode(base64_data)
        nparr = np.frombuffer(img_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    except Exception as e:
        print(f"Error decoding image: {e}")
        return base64_str
    
    if image is None:
        print("Could not decode image with OpenCV")
        return base64_str

    # 1. Find the white paper
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (15, 15), 0)
    
    # Otsu's thresholding automatically calculates the best threshold
    # Since receipts are generally white/bright against a darker background
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # If the background is bright and the receipt is darker, Otsu might assign 255 to background.
    # We check the border of the image. If the border is mostly 255, we invert the mask.
    border_pixels = np.concatenate((thresh[0,:], thresh[-1,:], thresh[:,0], thresh[:,-1]))
    if np.mean(border_pixels) > 127:
        thresh = cv2.bitwise_not(thresh)
        
    # Morphological closing to fill in the black text holes inside the receipt mask
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 25))
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    # Find contours of the white mask
    cnts, _ = cv2.findContours(closed.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = sorted(cnts, key=cv2.contourArea, reverse=True)
    
    if cnts:
        c = cnts[0] # The largest dense blob (should be the receipt with text)
        
        # Lowered to 2% of image area to support long/far away receipts
        if cv2.contourArea(c) > (image.shape[0] * image.shape[1] * 0.02):
            x, y, w, h = cv2.boundingRect(c)
            
            crop_x1 = max(0, x)
            crop_x2 = min(image.shape[1], x + w)
            crop_y1 = max(0, y)
            crop_y2 = image.shape[0] # Drop the bottom to the end of the image
            
            processed_image = image[crop_y1:crop_y2, crop_x1:crop_x2]
        else:
            processed_image = image
    else:
        processed_image = image

    # 2. Text Orientation Correction
    pil_img = Image.fromarray(cv2.cvtColor(processed_image, cv2.COLOR_BGR2RGB))
    
    try:
        # Require reasonable confidence to avoid random rotations from noisy images
        # Notice we set custom config for tesseract
        osd = pytesseract.image_to_osd(pil_img, config='--psm 0 -c min_characters_to_try=5')
        
        angle_match = re.search(r'Rotate: (\d+)', osd)
        if angle_match:
            angle = int(angle_match.group(1))
            if angle != 0:
                print(f"Rotating image {angle} degrees to correct orientation")
                # Tesseract 'Rotate: x' means we need to rotate CCW by x to be upright.
                # PIL's rotate() method uses CCW degrees.
                # However, for 90/270 degrees, expand=True is required to adapt dimensions
                pil_img = pil_img.rotate(-angle, expand=True) 
    except Exception as e:
        print(f"PyTesseract orientation detection error (could be no text): {e}")

    # Convert back to base64
    buffered = io.BytesIO()
    # Always save as JPEG to maintain valid format
    pil_img.save(buffered, format="JPEG", quality=85)
    img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    
    return f"{header}{img_b64}"
