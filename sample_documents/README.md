# Sample Documents for Testing OCR

This folder contains sample documents for testing the OCR functionality.

## Document Types

### Health Claims
- `medical_receipt.jpg` - Sample medical invoice
- `prescription.png` - Sample prescription document
- `hospital_bill.pdf` - Sample hospital bill

### Auto Claims
- `accident_photo.jpg` - Photo of vehicle damage
- `police_report.pdf` - Sample police report
- `repair_estimate.jpg` - Sample repair estimate

### Home Claims
- `damage_photo.jpg` - Photo of property damage
- `repair_invoice.pdf` - Sample repair invoice

## For Hackathon Demo

You can create sample documents with text using any tool, or use these placeholder instructions:

1. **Create a medical receipt**: Take a photo of any receipt with text
2. **Create a document**: Write claim details on paper and take a photo
3. **Use online tools**: Generate sample invoices online and save as images

## Testing OCR

Upload documents to the claim submission form. The system will:
1. Extract text using Gemini Vision API
2. Verify details match the claim
3. Check for inconsistencies
4. Provide confidence scores

## File Naming Convention

Use descriptive names:
- `{claim_type}_{document_type}_{date}.{ext}`
- Example: `health_receipt_2025-11-15.jpg`
