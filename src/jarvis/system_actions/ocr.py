"""
OCR system action module.

Provides OCR capabilities using pytesseract and Windows OCR APIs while enforcing
dry-run semantics and safety checks.
"""

import logging
import tempfile
from pathlib import Path
from typing import Optional, Tuple

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

try:
    import pytesseract
    from PIL import Image
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False

try:
    import ctypes
    from ctypes import wintypes
    WINDOWS_OCR_AVAILABLE = True
except ImportError:
    WINDOWS_OCR_AVAILABLE = False

from jarvis.action_executor import ActionResult

logger = logging.getLogger(__name__)


class OCRActions:
    """
    OCR system actions.

    Provides text extraction from images using pytesseract and Windows OCR APIs.
    """

    def __init__(self, dry_run: bool = False, tesseract_path: Optional[str] = None) -> None:
        """
        Initialize OCR actions.

        Args:
            dry_run: If True, preview actions without executing
            tesseract_path: Optional path to tesseract executable
        """
        self.dry_run = dry_run
        self.tesseract_path = tesseract_path
        
        if tesseract_path and PYTESSERACT_AVAILABLE:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
            
        if PYAUTOGUI_AVAILABLE:
            pyautogui.FAILSAFE = True
            pyautogui.PAUSE = 0.1
            
        logger.info("OCRActions initialized")

    def extract_text_from_image(self, image_path: str, language: str = "eng") -> ActionResult:
        """
        Extract text from an image file using pytesseract.

        Args:
            image_path: Path to the image file
            language: Language code for OCR (default: 'eng' for English)

        Returns:
            ActionResult with extracted text or error
        """
        logger.info(f"Extracting text from image: {image_path}")
        
        if not PYTESSERACT_AVAILABLE:
            return ActionResult(
                success=False,
                action_type="extract_text_from_image",
                message="pytesseract not available",
                error="Install pytesseract and pillow to use OCR features"
            )

        if self.dry_run:
            return ActionResult(
                success=True,
                action_type="extract_text_from_image",
                message=f"[DRY-RUN] Would extract text from {image_path}",
                data={"image_path": image_path, "language": language, "dry_run": True}
            )

        try:
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image, lang=language)
            
            return ActionResult(
                success=True,
                action_type="extract_text_from_image",
                message=f"Extracted {len(text)} characters from {image_path}",
                data={
                    "text": text,
                    "image_path": image_path,
                    "language": language,
                    "character_count": len(text),
                    "word_count": len(text.split())
                }
            )
        except Exception as e:
            logger.error(f"Error extracting text from image: {e}")
            return ActionResult(
                success=False,
                action_type="extract_text_from_image",
                message="Failed to extract text from image",
                error=str(e)
            )

    def extract_text_from_screen(
        self, region: Optional[Tuple[int, int, int, int]] = None, language: str = "eng"
    ) -> ActionResult:
        """
        Extract text from screen (or region) using pytesseract.

        Args:
            region: Optional (left, top, width, height) tuple for region capture
            language: Language code for OCR (default: 'eng' for English)

        Returns:
            ActionResult with extracted text or error
        """
        logger.info(f"Extracting text from screen (region={region})")
        
        if not PYAUTOGUI_AVAILABLE:
            return ActionResult(
                success=False,
                action_type="extract_text_from_screen",
                message="pyautogui not available",
                error="Install pyautogui to use screen OCR features"
            )

        if not PYTESSERACT_AVAILABLE:
            return ActionResult(
                success=False,
                action_type="extract_text_from_screen",
                message="pytesseract not available",
                error="Install pytesseract and pillow to use OCR features"
            )

        if self.dry_run:
            return ActionResult(
                success=True,
                action_type="extract_text_from_screen",
                message=f"[DRY-RUN] Would extract text from screen (region={region})",
                data={"region": region, "language": language, "dry_run": True}
            )

        try:
            # Capture screenshot
            if region:
                screenshot = pyautogui.screenshot(region=region)
            else:
                screenshot = pyautogui.screenshot()

            # Extract text
            text = pytesseract.image_to_string(screenshot, lang=language)
            
            return ActionResult(
                success=True,
                action_type="extract_text_from_screen",
                message=f"Extracted {len(text)} characters from screen",
                data={
                    "text": text,
                    "region": region,
                    "language": language,
                    "character_count": len(text),
                    "word_count": len(text.split())
                }
            )
        except Exception as e:
            logger.error(f"Error extracting text from screen: {e}")
            return ActionResult(
                success=False,
                action_type="extract_text_from_screen",
                message="Failed to extract text from screen",
                error=str(e)
            )

    def extract_text_with_boxes(
        self, image_path: str, language: str = "eng"
    ) -> ActionResult:
        """
        Extract text with bounding box information from an image.

        Args:
            image_path: Path to the image file
            language: Language code for OCR (default: 'eng' for English)

        Returns:
            ActionResult with text and bounding box data or error
        """
        logger.info(f"Extracting text with boxes from image: {image_path}")
        
        if not PYTESSERACT_AVAILABLE:
            return ActionResult(
                success=False,
                action_type="extract_text_with_boxes",
                message="pytesseract not available",
                error="Install pytesseract and pillow to use OCR features"
            )

        if self.dry_run:
            return ActionResult(
                success=True,
                action_type="extract_text_with_boxes",
                message=f"[DRY-RUN] Would extract text with boxes from {image_path}",
                data={"image_path": image_path, "language": language, "dry_run": True}
            )

        try:
            image = Image.open(image_path)
            data = pytesseract.image_to_data(image, lang=language, output_type=pytesseract.Output.DICT)
            
            # Process the data to extract text with bounding boxes
            boxes = []
            full_text = ""
            
            for i in range(len(data['text'])):
                text = data['text'][i].strip()
                if text:
                    box = {
                        "text": text,
                        "left": data['left'][i],
                        "top": data['top'][i],
                        "width": data['width'][i],
                        "height": data['height'][i],
                        "confidence": data['conf'][i]
                    }
                    boxes.append(box)
                    full_text += text + " "
            
            return ActionResult(
                success=True,
                action_type="extract_text_with_boxes",
                message=f"Extracted {len(boxes)} text elements from {image_path}",
                data={
                    "text": full_text.strip(),
                    "boxes": boxes,
                    "image_path": image_path,
                    "language": language,
                    "element_count": len(boxes)
                }
            )
        except Exception as e:
            logger.error(f"Error extracting text with boxes: {e}")
            return ActionResult(
                success=False,
                action_type="extract_text_with_boxes",
                message="Failed to extract text with boxes",
                error=str(e)
            )

    def get_available_languages(self) -> ActionResult:
        """
        Get list of available OCR languages.

        Returns:
            ActionResult with available languages or error
        """
        logger.info("Getting available OCR languages")
        
        if not PYTESSERACT_AVAILABLE:
            return ActionResult(
                success=False,
                action_type="get_available_languages",
                message="pytesseract not available",
                error="Install pytesseract to get available languages"
            )

        try:
            languages = pytesseract.get_languages(config='')
            return ActionResult(
                success=True,
                action_type="get_available_languages",
                message=f"Found {len(languages)} available languages",
                data={"languages": languages, "count": len(languages)}
            )
        except Exception as e:
            logger.error(f"Error getting available languages: {e}")
            return ActionResult(
                success=False,
                action_type="get_available_languages",
                message="Failed to get available languages",
                error=str(e)
            )

    def windows_ocr_from_screen(
        self, region: Optional[Tuple[int, int, int, int]] = None
    ) -> ActionResult:
        """
        Extract text from screen using Windows OCR API.

        Args:
            region: Optional (left, top, width, height) tuple for region capture

        Returns:
            ActionResult with extracted text or error
        """
        logger.info(f"Extracting text using Windows OCR (region={region})")
        
        if not WINDOWS_OCR_AVAILABLE:
            return ActionResult(
                success=False,
                action_type="windows_ocr_from_screen",
                message="Windows OCR API not available",
                error="Windows OCR API only available on Windows"
            )

        if self.dry_run:
            return ActionResult(
                success=True,
                action_type="windows_ocr_from_screen",
                message=f"[DRY-RUN] Would extract text using Windows OCR (region={region})",
                data={"region": region, "dry_run": True}
            )

        # Note: Windows OCR API implementation would require more complex COM interface
        # This is a placeholder that falls back to pytesseract for now
        if PYTESSERACT_AVAILABLE:
            return self.extract_text_from_screen(region)
        else:
            return ActionResult(
                success=False,
                action_type="windows_ocr_from_screen",
                message="Windows OCR not implemented and pytesseract not available",
                error="Install pytesseract for OCR functionality"
            )