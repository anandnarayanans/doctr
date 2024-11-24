import pdfplumber
import pytesseract
from PIL import Image, ImageDraw, ImageFont
from transformers import MarianMTModel, MarianTokenizer
import numpy as np
from io import BytesIO

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Load the MarianMT model and tokenizer for Arabic to English translation
model_name = 'Helsinki-NLP/opus-mt-ar-en'
tokenizer = MarianTokenizer.from_pretrained(model_name)
model = MarianMTModel.from_pretrained(model_name)

def translate_arabic_to_english(model, tokenizer, lines):
    """Translate Arabic text to English using MarianMT model."""
    translated_lines = []
    for line in lines:
        translated = model.generate(**tokenizer(line, return_tensors="pt", padding=True))
        translated_text = tokenizer.batch_decode(translated, skip_special_tokens=True)[0]
        translated_lines.append(translated_text)
    return translated_lines

def trans_image_ocr(image_bytes):
    """Perform OCR on an image and translate text, maintaining symbol integrity."""
    try:
        img_stream = BytesIO(image_bytes)
        image = Image.open(img_stream).convert("RGB")
        image_np = np.array(image)

        data = pytesseract.image_to_data(image_np, lang='ara+eng', config='--psm 6', output_type=pytesseract.Output.DICT)
        draw = ImageDraw.Draw(image)

        def contains_arabic(text):
            return any('\u0600' <= char <= '\u06FF' for char in text)

        contains_text = False

        for i in range(len(data['text'])):
            text = data['text'][i].strip()
            if text:
                contains_text = True
                
                # Determine replacement text
                if contains_arabic(text):
                    replacement_text = translate_arabic_to_english(model, tokenizer, [text])[0]
                elif text.isalpha():  # Keep English text unchanged
                    replacement_text = text
                else:  # Preserve symbols
                    replacement_text = text
                
                # Overlay translated/replacement text
                x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                draw.rectangle([x, y, x + w, y + h], fill="white")  # Cover the original text
                font_size = int(h * 0.9)  # Match size with the detected box

                try:
                    font = ImageFont.truetype("Helvetica.ttf", font_size)
                except:
                    font = ImageFont.load_default()

                # Ensure text fits the width of the original box
                while font.getbbox(replacement_text)[2] > w and font_size > 1:
                    font_size -= 1
                    font = ImageFont.truetype("Helvetica.ttf", font_size)

                draw.text((x, y), replacement_text, fill="black", font=font)

        if not contains_text:
            return image_bytes, "No text detected."

        # Save the modified image back to bytes
        output = BytesIO()
        image.save(output, format='PNG')
        output.seek(0)
        return output.read(), "Text successfully translated and modified."

    except Exception as e:
        return image_bytes, f"Error: {str(e)}"

def extract_images_from_pdf(pdf_path):
    """Extract images from a PDF using pdfplumber."""
    images = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                for image in page.images:
                    try:
                        img_bbox = (image["x0"], image["top"], image["x1"], image["bottom"])
                        img_obj = page.within_bbox(img_bbox).to_image(resolution=300)
                        img_data = BytesIO()
                        img_obj.save(img_data, format='PNG')
                        img_data.seek(0)
                        img_bytes = img_data.read()
                        images.append((img_bbox, img_bytes))
                    except Exception as e:
                        print(f"Error processing image: {e}")
    except Exception as e:
        print(f"Error extracting images from PDF: {e}")
    return images

# Example usage
pdf_path = "1.pdf"
extracted_images = extract_images_from_pdf(pdf_path)

if extracted_images:
    for idx, (bbox, img_bytes) in enumerate(extracted_images):
        modified_image, message = trans_image_ocr(img_bytes)
        with open(f"output_image_{idx + 1}.png", "wb") as output_file:
            output_file.write(modified_image)
        print(message)
else:
    print("No images found in the PDF.")
