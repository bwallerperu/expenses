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

    # 1. Edge Detection & Contour Cropping
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 50, 150)
    
    # Thicken edges to close gaps
    edged = cv2.dilate(edged, None, iterations=1)
    edged = cv2.erode(edged, None, iterations=1)

    # Find contours
    cnts, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:5]
    
    screenCnt = None
    if cnts:
        c = cnts[0] # The largest contour
        # Process if contour is at least 5% of the image area
        if cv2.contourArea(c) > (image.shape[0] * image.shape[1] * 0.05):
            peri = cv2.arcLength(c, True)
            
            # Try varying epsilons for exact 4-point match
            for eps in [0.02, 0.03, 0.04, 0.05]:
                approx = cv2.approxPolyDP(c, eps * peri, True)
                if len(approx) == 4:
                    screenCnt = approx
                    break
            
            # If no exact 4-point match, fall back to minimum area bounding rectangle
            if screenCnt is None:
                rect = cv2.minAreaRect(c)
                box = cv2.boxPoints(rect)
                box = np.int32(box)
                screenCnt = box.reshape(4, 1, 2)

    if screenCnt is not None:
        # We found a contour, apply perspective transform
        pts = screenCnt.reshape(4, 2)
        
        # Order points: top-left, top-right, bottom-right, bottom-left
        rect = np.zeros((4, 2), dtype="float32")
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        
        (tl, tr, br, bl) = rect
        widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        maxWidth = max(int(widthA), int(widthB))
        
        heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        maxHeight = max(int(heightA), int(heightB))
        
        dst = np.array([
            [0, 0],
            [maxWidth - 1, 0],
            [maxWidth - 1, maxHeight - 1],
            [0, maxHeight - 1]
        ], dtype="float32")
        
        M = cv2.getPerspectiveTransform(rect, dst)
        processed_image = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
    else:
        # No suitable contour found, proceed with original image
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
