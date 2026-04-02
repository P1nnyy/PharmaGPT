import cv2
import numpy as np
import os
import logging

logger = logging.getLogger(__name__)

def preprocess_image_for_ocr(image_path: str) -> bytes:
    """
    Preprocesses an image for OCR by correcting perspective and binarizing.
    
    Steps:
    1. Detect document corners and apply perspective warp ("flatten").
    2. Convert to grayscale and apply adaptive thresholding (binarization).
    3. Fallback to simple binarization if corner detection fails.
    
    Args:
        image_path (str): Path to the input image.
        
    Returns:
        bytes: Encoded image bytes (JPEG) of the processed image.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    try:
        # Load image
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Failed to load image: {image_path}")
            
        # 1. Automatic Rotation Correction
        img = correct_rotation(img)
            
        # 2. Convert to Grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 3. Apply Subtle Sharpening for OCR
        kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
        gray = cv2.filter2D(gray, -1, kernel)
        
        # Encode to bytes
        success, encoded_img = cv2.imencode('.jpg', gray)
        if not success:
            raise ValueError("Failed to encode processed image.")
            
        return encoded_img.tobytes()

    except Exception as e:
        logger.error(f"Image preprocessing failed: {e}")
        with open(image_path, "rb") as f:
            return f.read()

def correct_rotation(image):
    """
    Detects and corrects the orientation of the image (0, 90, 180, 270).
    Uses a multi-factor scoring system: 
    1. Text Line Alignment (Horizontal vs Vertical)
    2. Header vs Footer Asymmetry (Supplier info is at top)
    3. Vertical Line Detection (Tables should have vertical columns in portrait)
    """
    try:
        def get_orientation_score(img):
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else: gray = img
            
            h_img, w_img = img.shape[:2]
            # Thresholding for structural analysis
            thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
            
            # 1. Horizontal Text Score (Rows)
            # Most important: Horizontal line density for text
            k_w = max(40, w_img // 30)
            h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k_w, 1))
            horizontal = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, h_kernel)
            text_score = np.sum(horizontal) / 255
            
            # 2. Vertical Line Score (Columns - should be vertical in correct orientation)
            k_h = max(40, h_img // 30)
            v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, k_h))
            vertical = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, v_kernel)
            v_line_score = np.sum(vertical) / 255

            # 3. Asymmetry (Header Analysis)
            # Headers are in top 30%, Footers/Tables in bottom 70%
            # We look for "Large Blocks" (Supplier Name/Logos) in the top
            top_zone = thresh[0:int(h_img * 0.25), :]
            bot_zone = thresh[int(h_img * 0.75):, :]
            
            def get_block_complexity(zone):
                # Join characters into words/lines
                k = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 5))
                dilated = cv2.dilate(zone, k, iterations=1)
                cnts, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                score = 0
                for c in cnts:
                    bx, by, bw, bh = cv2.boundingRect(c)
                    # Headers are usually very wide (supplier name) and taller than body text
                    if bw > 150:
                        # Larger Weight for tall/wide text blocks (Headers)
                        score += (bw * bh)
                return score

            top_h_score = get_block_complexity(top_zone)
            bot_h_score = get_block_complexity(bot_zone)
            
            # Bias Calculation
            bias = 1.0
            # If the top has significantly more "header-like" blocks than the bottom
            # In an upside down image, the bot_h_score will be high because it contains the physical top.
            if top_h_score > bot_h_score * 2.0:
                bias = 3.0 # Top looks like a header
            elif bot_h_score > top_h_score * 2.0:
                bias = 0.3 # Bottom looks like a header (Upside down!)
                
            # Final scoring: Vertical lines are also a strong signal for portrait
            return (text_score + (v_line_score * 2.0)) * bias

        # Test orientations
        orientations = [
            (0, image),
            (90, cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)),
            (180, cv2.rotate(image, cv2.ROTATE_180)),
            (270, cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE))
        ]
        
        best_score = -1
        best_img = image
        best_angle = 0
        
        for angle, img in orientations:
            score = get_orientation_score(img)
            # Orientation Preference: Portrait is standard for invoices
            h, w = img.shape[:2]
            if h > w: 
                score *= 2.0 # Strong portrait bias
            
            if score > best_score:
                best_score = score
                best_img = img
                best_angle = angle
        
        logger.info(f"ImageProcessing: Auto-Rotation determined {best_angle}° (Final Score: {best_score:.0f})")
        return best_img

    except Exception as e:
        logger.warning(f"Rotation correction failed: {e}")
        return image

    except Exception as e:
        logger.warning(f"Rotation correction failed: {e}")
        return image

def enforce_portrait_rotation(image_path: str):
    """
    Standalone utility to fix a stored image file's orientation.
    Used during upload to ensure the UI shows a portrait view.
    """
    try:
        if not os.path.exists(image_path):
            return
            
        img = cv2.imread(image_path)
        if img is None:
            return
            
        fixed_img = correct_rotation(img)
        
        # Overwrite the original file
        cv2.imwrite(image_path, fixed_img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        logger.info(f"ImageProcessing: Successfully enforced portrait orientation for {image_path}")
        
    except Exception as e:
        logger.error(f"Failed to enforce portrait orientation for {image_path}: {e}")

def _flatten_document(img, gray):
    """
    Attempts to find the document contours and warp perspective.
    Returns warped image or None if failed.
    """
    try:
        # Blur and Edges (Adaptive Canny)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Try finding edges with automatic thresholding using median
        v = np.median(gray)
        sigma = 0.33
        lower = int(max(0, (1.0 - sigma) * v))
        upper = int(min(255, (1.0 + sigma) * v))
        edged = cv2.Canny(blurred, lower, upper)
        
        # Dialate to close gaps
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        edged = cv2.dilate(edged, kernel, iterations=1)
        
        # Find Contours
        contours, _ = cv2.findContours(edged.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
        
        screen_cnt = None
        
        # Strategy 1: Iterative Approximation to find 4 corners
        for c in contours:
            peri = cv2.arcLength(c, True)
            # Try different epsilons to smooth out edges
            for epsilon_factor in [0.02, 0.05, 0.08]:
                approx = cv2.approxPolyDP(c, epsilon_factor * peri, True)
                if len(approx) == 4:
                    screen_cnt = approx
                    break
            if screen_cnt is not None:
                break
                
        # Strategy 2: Fallback to largest bounding box
        if screen_cnt is None and len(contours) > 0:
            c = contours[0]
            x, y, w, h = cv2.boundingRect(c)
            # Only use if it covers a significant portion of the image (e.g. > 10%)
            img_area = img.shape[0] * img.shape[1]
            if (w * h) > (0.1 * img_area):
                screen_cnt = np.array([[x, y], [x+w, y], [x+w, y+h], [x, y+h]])
            
        if screen_cnt is None:
            return None
            
        # Warp
        warped = _four_point_transform(img, screen_cnt.reshape(4, 2))
        return warped
        
    except Exception:
        return None

def _four_point_transform(image, pts):
    """
    Applies perspective transform and ensures high resolution.
    """
    rect = _order_points(pts)
    (tl, tr, br, bl) = rect

    # Compute width of new image
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))

    # Compute height of new image
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))
    
    # ENLARGE: Ensure minimum width of 3000px for better OCR
    target_width = max(maxWidth, 3000)
    scale_ratio = target_width / maxWidth
    target_height = int(maxHeight * scale_ratio)

    dst = np.array([
        [0, 0],
        [target_width - 1, 0],
        [target_width - 1, target_height - 1],
        [0, target_height - 1]], dtype = "float32")

    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (target_width, target_height))
    
    # Sharpening kernel for better OCR
    kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    warped = cv2.filter2D(warped, -1, kernel)

    return warped

def _order_points(pts):
    """
    Orders points: top-left, top-right, bottom-right, bottom-left
    """
    rect = np.zeros((4, 2), dtype = "float32")
    s = pts.sum(axis = 1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]

    diff = np.diff(pts, axis = 1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]

    return rect
