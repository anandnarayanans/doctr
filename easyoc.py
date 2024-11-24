import easyocr
from googletrans import Translator

# Initialize the EasyOCR reader with Arabic and English languages
reader = easyocr.Reader(['ar', 'en'])

# Path to the image containing Arabic text
image_path = 'a.png'

# Read the text from the image
result = reader.readtext(image_path)

# Extract and print the Arabic text
arabic_text = ' '.join([res[1] for res in result])
print("Arabic Text: ", arabic_text)

# Translate the Arabic text to English using Google Translate API
translator = Translator()
translation = translator.translate(arabic_text, src='ar', dest='en')

# Print the translated text
print("Translated Text: ", translation.text)