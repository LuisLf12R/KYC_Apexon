def cleanup(ocr_text: str) -> dict:
    lines = ocr_text.strip().split('\n')
    
    result = {
        'statement_date': None,
        'account_holder_name': None,
        'account_holder_address': None,
        'account_number': None,
        'transaction_date': [],
        'transaction_description': [],
        'transaction_type': [],
        'transaction_amount': [],
        'balance': []
    }
    
    # Extract statement date
    for line in lines:
        if 'Statement Date:' in line:
            date_part = line.split('Statement Date:')[1].strip()
            result['statement_date'] = date_part
            break
    
    # Extract account number
    for line in lines:
        if 'Account Number:' in line:
            acc_part = line.split('Account Number:')[1].strip()
            result['account_number'] = acc_part
            break
    
    # Extract account holder name and address
    # Name is typically after bank name and before address
    name_found = False
    address_lines = []
    for i, line in enumerate(lines):
        if 'Statement Date:' in line and i + 1 < len(lines):
            # Next non-empty line after statement date is usually the name
            for j in range(i + 1, min(i + 6, len(lines))):
                if lines[j].strip() and not any(keyword in lines[j] for keyword in ['BANK', 'STATEMENT', 'Account']):
                    if not name_found:
                        result['account_holder_name'] = lines[j].strip()
                        name_found = True
                    elif 'ACCOUNT' not in lines[j].upper():
                        address_lines.append(lines[j].strip())
                    if 'ACCOUNT' in lines[j].upper():
                        break
            break
    
    if address_lines:
        result['account_holder_address'] = ', '.join(address_lines)
    
    # Extract transactions
    in_transaction_section = False
    for i, line in enumerate(lines):
        if 'Date' in line and 'Description' in line and 'Type' in line and 'Amount' in line:
            in_transaction_section = True
            continue
            
        if in_transaction_section and line.strip():
            # Parse transaction line
            parts = line.split()
            if len(parts) >= 4:
                # Check if first part looks like a date (YYYY-MM-DD format)
                if len(parts[0]) == 10 and parts[0].count('-') == 2:
                    date = parts[0]
                    
                    # Find where the amount starts (starts with +, -, or $)
                    amount_idx = -1
                    balance_idx = -1
                    for j in range(len(parts) - 1, 0, -1):
                        if parts[j].startswith(('$', '+$', '-$')) or (j > 0 and parts[j-1] in ['+', '-'] and parts[j].startswith('$')):
                            if balance_idx == -1:
                                balance_idx = j
                            else:
                                amount_idx = j
                                break
                    
                    # Extract transaction type (Credit/Debit)
                    trans_type = None
                    for j in range(1, len(parts)):
                        if parts[j].lower() in ['credit', 'debit']:
                            trans_type = parts[j].capitalize()
                            type_idx = j
                            break
                    
                    if trans_type and amount_idx > 0:
                        # Description is between date and type
                        description = ' '.join(parts[1:type_idx])
                        
                        # Amount
                        if parts[amount_idx-1] in ['+', '-'] and amount_idx > 0:
                            amount = parts[amount_idx-1] + parts[amount_idx]
                        else:
                            amount = parts[amount_idx]
                        
                        # Balance
                        balance = parts[balance_idx] if balance_idx > amount_idx else None
                        
                        result['transaction_date'].append(date)
                        result['transaction_description'].append(description.strip())
                        result['transaction_type'].append(trans_type)
                        result['transaction_amount'].append(amount)
                        if balance:
                            result['balance'].append(balance)
    
    # Clean up OCR errors
    for key in result:
        if isinstance(result[key], str):
            result[key] = result[key].replace('l', '1').replace('O', '0') if key == 'account_number' else result[key]
    
    return result