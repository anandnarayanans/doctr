import os
import threading
import pdfplumber
import arabic_reshaper
from bidi.algorithm import get_display
from transformers import MarianMTModel, MarianTokenizer
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from io import BytesIO
import re
import tempfile
from datetime import datetime
import random
import string
# from langdetect import detect, DetectorFactory
from PIL import Image, ImageDraw, ImageFont
import easyocr
from google.colab import files

# Store translations in memory
translations = {}

def generate_random_username():
    """Generate a random username."""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

def extract_text_images_tables_from_pdf(pdf_path):
    """Extract text, images, and tables from a PDF file."""
    extracted_content = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_content = {"text": "", "translated_text": "", "images": [], "tables": []}
            text = page.extract_text(x_tolerance=2, y_tolerance=2)
            if text:
                bidi_text = get_display(arabic_reshaper.reshape(text))
                page_content["text"] = bidi_text

            # Extract images with their positions
            for image in page.images:
                try:
                    img_bbox = (image["x0"], image["top"], image["x1"], image["bottom"])
                    img_obj = page.within_bbox(img_bbox).to_image(resolution=300)
                    img_data = BytesIO()
                    img_obj.save(img_data, format='PNG')
                    img_data.seek(0)
                    img_bytes = img_data.read()
                    # Store both position and image data
                    page_content["images"].append({
                        "bbox": img_bbox,
                        "image": img_bytes,
                        "width": image["width"],
                        "height": image["height"]
                    })
                except Exception as e:
                    print(f"Error processing image: {e}")
                    continue

            tables = page.extract_tables()
            for table in tables:
                reshaped_table = []
                for row in table:
                    reshaped_row = [get_display(arabic_reshaper.reshape(cell)) if cell else '' for cell in row]
                    reshaped_table.append(reshaped_row)
                page_content["tables"].append(reshaped_table)

            extracted_content.append(page_content)
    return extracted_content

from PIL import Image, ImageDraw, ImageFont
import numpy as np
from io import BytesIO
import easyocr

from PIL import Image, ImageDraw, ImageFont
import numpy as np
from io import BytesIO
import easyocr

def trans_image_ocr(image_bytes):
    """Perform OCR on an image, handle both Arabic and English text with proper formatting."""
    try:
        reader = easyocr.Reader(['ar', 'en'])
        img_stream = BytesIO(image_bytes)
        image = Image.open(img_stream).convert("RGB")
        
        # Perform OCR
        results = reader.readtext(np.array(image))
        
        # Create a drawing object
        draw = ImageDraw.Draw(image)
        
        # Common substitutions for OCR mistakes
        ocr_corrections = {
            'R5YAL': 'ROYAL',
            'C5MMISSI5N': 'COMMISSION',
            'M4KK4H': 'MAKKAH',
            'CITV': 'CITY',
            '4NL': 'AND',
            'HLY': 'HOLY',
            '5': 'O',
            '4': 'A',
            'V': 'Y'
        }
        
        all_translated_text = []
        contains_text = False
        
        for bbox, text, confidence in results:
            contains_text = True
            
            # Check if text contains Arabic characters
            if any('\u0600' <= char <= '\u06FF' for char in text):
                # Translate Arabic text to English
                final_text = translate_arabic_to_english(model, tokenizer, [text])[0]
            else:
                # Apply global replacements for known OCR issues
                for wrong, right in ocr_corrections.items():
                    text = text.replace(wrong, right)  # Replace full patterns globally
                
                # Replace any remaining '5' with 'O' in the entire string
                text = text.replace('5', 'O')

                # Ensure final corrections are applied at the character level
                corrected_text = ''
                for char in text:
                    corrected_text += ocr_corrections.get(char, char)
                
                final_text = corrected_text
                
                # Special case for known phrases
                if any(phrase in final_text for phrase in ['ROYAL COMMISSION', 'MAKKAH CITY', 'HOLY SITES']):
                    # Preserve exact casing and formatting for official names
                    final_text = final_text.upper()
                else:
                    # For other English text, ensure proper capitalization
                    final_text = ' '.join(word.capitalize() for word in final_text.split())
            
            all_translated_text.append(final_text)
            
            # Get coordinates for text replacement
            x_min = min(p[0] for p in bbox)
            y_min = min(p[1] for p in bbox)
            x_max = max(p[0] for p in bbox)
            y_max = max(p[1] for p in bbox)
            
            # Create white background for clarity
            draw.rectangle([x_min, y_min, x_max, y_max], fill="white")
            
            # Calculate original text height to maintain font size
            text_height = y_max - y_min
            font_size = int(text_height * 0.62)  # Adjust this factor if needed
            
            # Draw text with consistent font
            try:
                font = ImageFont.truetype("Helvetica.ttf", font_size)
            except:
                font = ImageFont.load_default()
            
            # Draw the text
            draw.text((x_min, y_min), final_text, fill="black", font=font)
        
        # Return original image if no text was found
        if not contains_text:
            return image_bytes, ""
        
        # Convert modified image back to bytes
        output = BytesIO()
        image.save(output, format='PNG')
        output.seek(0)
        
        return output.read(), ""
    
    except Exception as e:
        print(f"Error in trans_image_ocr: {e}")
        return image_bytes, ""  #

def translate_arabic_to_english(model, tokenizer, lines):
    """Translate Arabic text to English using MarianMT model."""
    translated_lines = []
    for line in lines:
        translated = model.generate(**tokenizer(line, return_tensors="pt", padding=True))
        translated_text = tokenizer.batch_decode(translated, skip_special_tokens=True)[0]
        translated_lines.append(translated_text)
    return translated_lines

def clean_translation(text):
    """Clean the translated text to remove unwanted artifacts."""
    cleaned_text = re.sub(r'\b(?:no|not|non-|, ,)\b', '', text, flags=re.IGNORECASE).strip()
    return cleaned_text

def save_text_images_tables_to_pdf(pages_content, output_pdf_path, model, tokenizer):
    """Save the given text, images, and tables to a PDF file."""
    c = canvas.Canvas(output_pdf_path, pagesize=letter)
    width, height = letter
    styles = getSampleStyleSheet()
    styleN = styles['Normal']
    left_margin, right_margin = 35, 35
    current_font_size = 11
    
    for page_content in pages_content:
        y = height - 40
        
        # Process and draw images with translated text
        for img_data in page_content["images"]:
            # Get the original image data and position
            img_bytes = img_data["image"]
            img_bbox = img_data["bbox"]
            
            # Translate and modify the image
            modified_img_bytes, _  = trans_image_ocr(img_bytes)
            
            # Draw the modified image
            try:
                img_stream = BytesIO(modified_img_bytes)
                img = ImageReader(img_stream)
    
        # Use original bounding box coordinates to draw the image
                x0, y0, x1, y1 = img_bbox
                img_width = x1 - x0
                img_height = y1 - y0
                
                # Translate PDF coordinate system (y-axis inverted)
                y_draw = height - y1

              
                
                # Draw the modified image
                c.drawImage(img, x0, y_draw, width=img_width, height=img_height)
                # c.drawImage(img, left_margin, y - img_height, width=img_width, height=img_height)
                y -= img_height + 15
                
            except Exception as e:
                print(f"Error drawing image: {e}")
                continue

        c.setFont("Helvetica", current_font_size)
        translated_text = page_content["translated_text"]
        translated_lines = translated_text.split('\n')
 
        # Variables for list detection
        in_numbered_list = False
        in_address_list = False
        next_line_starts_address_list = False

        i = 0
        while i < len(translated_lines):
            line = translated_lines[i]
            
            # Check for numbered list start
            starts_with_number = line.strip() and line.strip()[0].isdigit() and '.' in line.strip()[:3]

            # Check for address-based list start in next line
            if "address" in line.lower() and ":" in line:
                if i > 0:
                    y -= 15  # Line break above the sentence before the address-based list
                next_line_starts_address_list = True
            elif next_line_starts_address_list:
                in_address_list = True
                next_line_starts_address_list = False
            
            # Detect sentences with ':' and '-' and handle line breaks
            if ":" in line and "-" in line:
                if i < len(translated_lines) - 1 and translated_lines[i + 1].strip()[0].isdigit():
                    y -= 15  # Add a line break above the sentence

            # Handle list end conditions
            if in_numbered_list and not starts_with_number:
                in_numbered_list = False
                y -= 15  # Line break above detected list
            
            if in_address_list:
                words = line.split()
                if len(words) >= 14:  # Check for long sentence
                    in_address_list = False
                    y -= 15  # Line break above detected list
            
            # Check if the line contains a colon and handle it as a full sentence if so
            if ":" in line:
                colon_idx = line.index(":")
                sentence = line[:colon_idx + 1].strip().capitalize()
                remaining_text = line[colon_idx + 1:].strip()
               
                # Draw the bold sentence with word wrapping and a single space after the colon
                c.setFont("Helvetica-Bold", current_font_size)
                sentence_to_print = (sentence + ":" if sentence[-1] != ":" else sentence) + " "
               
                # Word wrapping for the bold sentence
                text_offset = left_margin
                for word in sentence_to_print.split():
                    if text_offset + c.stringWidth(word + " ") > (width - right_margin):
                        y -= 15
                        text_offset = left_margin
                    c.drawString(text_offset, y, word)
                    text_offset += c.stringWidth(word + " ")
 
                # Draw remaining text in normal font with word wrapping
                c.setFont("Helvetica", current_font_size)
                for word in remaining_text.split():
                    if text_offset + c.stringWidth(word + " ") > (width - right_margin):
                        y -= 15
                        text_offset = left_margin
                    c.drawString(text_offset, y, word)
                    text_offset += c.stringWidth(word + " ")
            else:
                # Draw the line as normal with word wrapping within the margins
                text_offset = left_margin
                for word in line.split():
                    if text_offset + c.stringWidth(word + " ") > (width - right_margin):
                        y -= 15
                        text_offset = left_margin
                    c.drawString(text_offset, y, word)
                    text_offset += c.stringWidth(word + " ")
 
            y -= 15  # Minimal space to the next line of text
 
            # Check for page break and prevent empty page creation
            if y < 40:
                if y == height - 40:  # Ensure the current page is not empty
                    break
                c.showPage()
                y = height - 40
                c.setFont("Helvetica", current_font_size)  # Maintain font size across pages
            
            i += 1
 
        # Draw tables with word wrapping in each cell
        for table in page_content["tables"]:
            table_style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('TOPPADDING', (0, 0), (-1, -1), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('WORDWRAP', (0, 0), (-1, -1), 'CJK')
            ])
 
            wrapped_table = []
            for row in table:
                wrapped_row = [Paragraph(cell, styleN) for cell in row]
                wrapped_table.append(wrapped_row)
 
            col_widths = [(width - left_margin - right_margin) / len(wrapped_table[0])] * len(wrapped_table[0])
            t = Table(wrapped_table, colWidths=col_widths)
            t.setStyle(table_style)
            w, h = t.wrap(width, y)
            if h > y:
                if y != height - 40:  # Avoid adding a new page if the current one is empty
                    c.showPage()
                y = height - 40
                c.setFont("Helvetica", current_font_size)  # Maintain font size across pages
            t.drawOn(c, left_margin, y - h)
            y -= h + 15
 
        if y != height - 40:  # Avoid adding unnecessary blank pages
            c.showPage()
 
    c.save()


def translate_pdf(file_path):
    """Translate a PDF file and save the output."""
    with pdfplumber.open(file_path) as pdf:
        first_page = pdf.pages[0]
        first_page_text = first_page.extract_text()
        if not first_page_text:
            raise ValueError("PDF contains no text.")

    model_name = 'Helsinki-NLP/opus-mt-ar-en'
    model = MarianMTModel.from_pretrained(model_name)
    tokenizer = MarianTokenizer.from_pretrained(model_name)

    pages_content = extract_text_images_tables_from_pdf(file_path)

    for page_content in pages_content:
        original_lines = page_content["text"].split("\n")
        translated_lines = translate_arabic_to_english(model, tokenizer, original_lines)
        cleaned_translated_text = "\n".join(clean_translation(line) for line in translated_lines)
        page_content["translated_text"] = cleaned_translated_text

    output_dir = 'translated_files'
    os.makedirs(output_dir, exist_ok=True)

    output_pdf_path = f'{output_dir}/{os.path.basename(file_path)}'
    save_text_images_tables_to_pdf(pages_content, output_pdf_path, model, tokenizer)

    translation_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    translation_id = generate_random_username()
    translations[translation_id] = {
        "file_name": os.path.basename(file_path),
        "translation_date": translation_time.split()[0],
        "translation_time": translation_time.split()[1],
        "output_path": output_pdf_path
    }
    return output_pdf_path, translation_id

def upload_and_translate():
    """Upload a file and translate it."""
    uploaded = files.upload()
    for filename in uploaded.keys():
        print(f"Uploaded file: {filename}")
        output_pdf_path, translation_id = translate_pdf(filename)
        print(f"Translation saved to: {output_pdf_path}")
        print(f"Translation ID: {translation_id}")

# Call the upload and translate function
upload_and_translate()