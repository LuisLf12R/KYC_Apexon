
def cleanup(ocr_text):
    """Extract KYC fields from OCR text"""
    lines = ocr_text.split('\n')
    result = {}
    
    # Simple parsing logic (in real use, Claude generates this)
    for i, line in enumerate(lines):
        if 'NORTHEAST ATLANTIC' in line:
            result['bank_name'] = 'NORTHEAST ATLANTIC RETAIL BANK'
        if 'Luis Romero' in line:
            result['name'] = 'Luis Romero'
        if 'New York' in line:
            result['city'] = 'New York'
    
    return result
