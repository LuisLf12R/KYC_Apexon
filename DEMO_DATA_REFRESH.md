# Demo Data Refresh Kit
**Use 5 minutes before the demo.** Copy each block into a new `.csv` file, upload all 6 via Batch upload, then hit Run batch.

- Customer IDs: `KYC-0051` → `KYC-0059`
- Expected results: **5 PASS · 2 REVIEW · 1 REJECT** (Ivan Lee starts as REVIEW — passport missing)
- Batch date: today
- Passport image: `~/Downloads/passport_KYC-0059_Ivan_Lee.png`

### Demo flow for document reconciliation (live in the room)
1. Upload all 6 CSVs → Run batch → Ivan Lee appears in Worklist as **REVIEW** (missing passport)
2. Go to Batch upload → drop `passport_KYC-0059_Ivan_Lee.png` → it auto-detects as Documents
3. Go back to Worklist → re-run batch → Ivan Lee upgrades to **PASS**

---

## 1. `customers.csv`

```
customer_id,full_name,jurisdiction,client_type,tier,risk_rating,onboarding_date,aum,relationship_manager,pep_flag,sanctions_flag,nationality,date_of_birth,country_of_residence,source_of_wealth,tax_id,crs_status,fatca_status
KYC-0051,Sophie Laurent,CH,INDIVIDUAL,UHNW,LOW,2025-11-12,2400000,A. Mercer,FALSE,FALSE,CH,1983-06-14,CH,INVESTMENT,CH48291034,COMPLIANT,NOT_APPLICABLE
KYC-0052,Meridian Capital Ltd,GB,CORPORATE,WEALTH,LOW,2025-08-03,890000,A. Mercer,FALSE,FALSE,GB,,GB,BUSINESS_INCOME,GB72184956,COMPLIANT,NOT_APPLICABLE
KYC-0053,Ahmad Al-Rashidi,AE,INDIVIDUAL,UHNW,HIGH,2024-05-19,5100000,A. Mercer,TRUE,FALSE,AE,1971-03-28,AE,INVESTMENT,AE30182746,NOT_APPLICABLE,NOT_APPLICABLE
KYC-0054,Chen Wei Holdings,SG,CORPORATE,FAMILY_OFFICE,LOW,2025-01-22,12000000,A. Mercer,FALSE,FALSE,SG,,SG,BUSINESS_INCOME,SG84710293,COMPLIANT,NOT_APPLICABLE
KYC-0055,Isabelle Fontaine,FR,INDIVIDUAL,WEALTH,LOW,2025-09-30,445000,A. Mercer,FALSE,FALSE,FR,1990-11-02,FR,EMPLOYMENT,FR29471823,COMPLIANT,NOT_APPLICABLE
KYC-0056,Viktor Drakov,RU,INDIVIDUAL,WEALTH,HIGH,2023-12-01,3200000,A. Mercer,FALSE,TRUE,RU,1968-07-17,RU,INVESTMENT,RU10293847,NON_COMPLIANT,NOT_APPLICABLE
KYC-0057,Haruki Tanaka,JP,INDIVIDUAL,UHNW,LOW,2025-06-14,8700000,A. Mercer,FALSE,FALSE,JP,1975-09-05,JP,INVESTMENT,JP93847561,COMPLIANT,NOT_APPLICABLE
KYC-0058,Carla Mendez Ortega,MX,INDIVIDUAL,WEALTH,MEDIUM,2024-10-08,1100000,A. Mercer,FALSE,FALSE,MX,1988-04-23,MX,EMPLOYMENT,MX47382910,COMPLIANT,NOT_APPLICABLE
KYC-0059,Ivan Lee,US,INDIVIDUAL,UHNW,LOW,2025-03-17,4750000,A. Mercer,FALSE,FALSE,US,1988-03-12,US,INVESTMENT,US84729103,COMPLIANT,COMPLIANT
```

---

## 2. `screenings.csv`

```
customer_id,screening_date,screening_result,risk_rating,resolution_status,resolution_date,match_name,match_score,list_reference
KYC-0051,2026-04-18,NO_MATCH,LOW,CLEARED,2026-04-18,,0,
KYC-0052,2026-04-15,NO_MATCH,LOW,CLEARED,2026-04-15,,0,
KYC-0053,2026-03-20,POSSIBLE_MATCH,HIGH,UNDER_REVIEW,,Ahmad Al-Rashid,72,PEP-WORLD
KYC-0054,2026-04-22,NO_MATCH,LOW,CLEARED,2026-04-22,,0,
KYC-0055,2026-04-10,NO_MATCH,LOW,CLEARED,2026-04-10,,0,
KYC-0056,2026-02-14,CONFIRMED_MATCH,HIGH,ESCALATED,,Viktor Drakovitch,95,OFAC-SDN
KYC-0057,2026-04-20,NO_MATCH,LOW,CLEARED,2026-04-20,,0,
KYC-0058,2026-03-31,POSSIBLE_MATCH,MEDIUM,UNDER_REVIEW,,C. Mendez,63,PEP-LATAM
KYC-0059,2026-04-25,NO_MATCH,LOW,CLEARED,2026-04-25,,0,
```

---

## 3. `transactions.csv`

```
customer_id,transaction_date,transaction_type,amount,currency,counterparty_country,is_suspicious,transaction_id,channel
KYC-0051,2026-04-01,WIRE_TRANSFER,120000,CHF,CH,FALSE,TXN-5001,ONLINE
KYC-0051,2026-04-14,INVESTMENT,850000,CHF,US,FALSE,TXN-5002,BRANCH
KYC-0052,2026-03-18,WIRE_TRANSFER,45000,GBP,GB,FALSE,TXN-5003,ONLINE
KYC-0052,2026-04-05,DEPOSIT,200000,GBP,GB,FALSE,TXN-5004,ONLINE
KYC-0053,2026-04-02,WIRE_TRANSFER,500000,USD,AE,FALSE,TXN-5005,BRANCH
KYC-0053,2026-04-19,INVESTMENT,1200000,USD,CH,FALSE,TXN-5006,BRANCH
KYC-0054,2026-03-25,WIRE_TRANSFER,2500000,SGD,SG,FALSE,TXN-5007,ONLINE
KYC-0054,2026-04-10,INVESTMENT,4000000,USD,US,FALSE,TXN-5008,BRANCH
KYC-0055,2026-04-08,DEPOSIT,18000,EUR,FR,FALSE,TXN-5009,ONLINE
KYC-0055,2026-04-21,WIRE_TRANSFER,32000,EUR,DE,FALSE,TXN-5010,ONLINE
KYC-0056,2026-01-15,WIRE_TRANSFER,750000,USD,RU,TRUE,TXN-5011,BRANCH
KYC-0056,2026-02-03,WIRE_TRANSFER,480000,USD,IR,TRUE,TXN-5012,BRANCH
KYC-0056,2026-03-09,CASH_DEPOSIT,95000,USD,RU,TRUE,TXN-5013,BRANCH
KYC-0057,2026-04-11,INVESTMENT,3100000,JPY,JP,FALSE,TXN-5014,ONLINE
KYC-0057,2026-04-25,WIRE_TRANSFER,620000,USD,US,FALSE,TXN-5015,ONLINE
KYC-0058,2026-03-14,DEPOSIT,55000,USD,MX,FALSE,TXN-5016,ONLINE
KYC-0058,2026-04-17,WIRE_TRANSFER,210000,USD,US,FALSE,TXN-5017,ONLINE
KYC-0059,2026-04-03,INVESTMENT,1800000,USD,US,FALSE,TXN-5018,ONLINE
KYC-0059,2026-04-22,WIRE_TRANSFER,340000,USD,CH,FALSE,TXN-5019,BRANCH
```

---

## 4. `documents.csv`

```
customer_id,document_type,document_id,upload_date,status,file_name,issuing_country,expiry_date
KYC-0051,PASSPORT,DOC-5001,2026-04-20,VERIFIED,sophie_laurent_passport.pdf,CH,2031-06-14
KYC-0051,PROOF_OF_ADDRESS,DOC-5002,2026-04-20,VERIFIED,sophie_laurent_utility.pdf,CH,2026-07-01
KYC-0052,CERTIFICATE_OF_INCORPORATION,DOC-5003,2026-04-18,VERIFIED,meridian_cap_cert.pdf,GB,2028-08-03
KYC-0052,PROOF_OF_ADDRESS,DOC-5004,2026-04-18,VERIFIED,meridian_cap_address.pdf,GB,2026-08-01
KYC-0053,PASSPORT,DOC-5005,2026-04-10,VERIFIED,ahmad_passport.pdf,AE,2029-03-28
KYC-0053,PROOF_OF_ADDRESS,DOC-5006,2026-04-10,PENDING,ahmad_address.pdf,AE,2026-06-01
KYC-0054,CERTIFICATE_OF_INCORPORATION,DOC-5007,2026-04-22,VERIFIED,chenwei_cert.pdf,SG,2027-01-22
KYC-0054,PROOF_OF_ADDRESS,DOC-5008,2026-04-22,VERIFIED,chenwei_address.pdf,SG,2026-10-01
KYC-0055,PASSPORT,DOC-5009,2026-04-19,VERIFIED,isabelle_passport.pdf,FR,2030-11-02
KYC-0055,PROOF_OF_ADDRESS,DOC-5010,2026-04-19,VERIFIED,isabelle_utility.pdf,FR,2026-07-15
KYC-0056,PASSPORT,DOC-5011,2026-03-01,EXPIRED,viktor_passport.pdf,RU,2025-07-17
KYC-0056,PROOF_OF_ADDRESS,DOC-5012,2026-03-01,REJECTED,viktor_address.pdf,RU,2025-12-01
KYC-0057,PASSPORT,DOC-5013,2026-04-21,VERIFIED,haruki_passport.pdf,JP,2032-09-05
KYC-0057,PROOF_OF_ADDRESS,DOC-5014,2026-04-21,VERIFIED,haruki_utility.pdf,JP,2026-09-01
KYC-0058,PASSPORT,DOC-5015,2026-04-16,VERIFIED,carla_passport.pdf,MX,2028-04-23
KYC-0058,PROOF_OF_ADDRESS,DOC-5016,2026-04-16,VERIFIED,carla_address.pdf,MX,2026-08-01
KYC-0059,PROOF_OF_ADDRESS,DOC-5017,2026-04-25,VERIFIED,ivan_lee_utility.pdf,US,2026-10-01
```

> **Note:** Ivan Lee has NO passport row here — that's intentional. His passport is uploaded separately as `passport_KYC-0059_Ivan_Lee.png` to demonstrate the document reconciliation flow.

---

## 5. `id_verifications.csv`

```
customer_id,document_type,verification_date,expiry_date,verification_method,name_on_document
KYC-0051,PASSPORT,2026-04-20,2031-06-14,BIOMETRIC,Sophie Laurent
KYC-0052,CERTIFICATE_OF_INCORPORATION,2026-04-18,2028-08-03,MANUAL,Meridian Capital Ltd
KYC-0053,PASSPORT,2026-04-10,2029-03-28,BIOMETRIC,Ahmad Al-Rashidi
KYC-0054,CERTIFICATE_OF_INCORPORATION,2026-04-22,2027-01-22,MANUAL,Chen Wei Holdings
KYC-0055,PASSPORT,2026-04-19,2030-11-02,BIOMETRIC,Isabelle Fontaine
KYC-0056,PASSPORT,2026-03-01,2025-07-17,MANUAL,Viktor Drakov
KYC-0057,PASSPORT,2026-04-21,2032-09-05,BIOMETRIC,Haruki Tanaka
KYC-0058,PASSPORT,2026-04-16,2028-04-23,BIOMETRIC,Carla Mendez Ortega
KYC-0059,PROOF_OF_ADDRESS,2026-04-25,2026-10-01,MANUAL,Ivan Lee
```

---

## 6. `beneficial_ownership.csv`

```
customer_id,ubo_name,ubo_dob,ubo_nationality,ownership_percent,ubo_role,ubo_pep_flag,ubo_sanctions_flag,ubo_jurisdiction,verification_date,chain_depth,parent_ownership_pct,control_type
KYC-0052,James Whitfield,1965-04-11,GB,100,DIRECTOR,FALSE,FALSE,GB,2026-04-18,1,100,DIRECT
KYC-0054,Chen Wei,1958-09-22,SG,72,CEO,FALSE,FALSE,SG,2026-04-22,1,72,DIRECT
KYC-0054,Linda Huang,1963-02-17,SG,28,CFO,FALSE,FALSE,SG,2026-04-22,1,28,DIRECT
KYC-0056,Viktor Drakov,1968-07-17,RU,100,SOLE_OWNER,FALSE,TRUE,RU,2026-03-01,1,100,DIRECT
```

> Ivan Lee is INDIVIDUAL — no beneficial ownership row needed.

---

## Why each decision fires

| Customer | Expected | Key signal |
|---|---|---|
| Sophie Laurent | ✅ PASS | Clean screening, verified docs, low risk |
| Meridian Capital | ✅ PASS | Clean corp, verified UBO |
| Ahmad Al-Rashidi | 🟡 REVIEW | PEP flag + unresolved screening match |
| Chen Wei Holdings | ✅ PASS | Large UHNW, clean screening, verified UBOs |
| Isabelle Fontaine | ✅ PASS | Clean individual, all docs current |
| Viktor Drakov | 🔴 REJECT | Sanctions flag, CONFIRMED_MATCH, expired docs, suspicious txns to Iran |
| Haruki Tanaka | ✅ PASS | Clean UHNW, biometric verified |
| Carla Mendez Ortega | 🟡 REVIEW | Unresolved PEP-LATAM match, MEDIUM risk |
| Ivan Lee | 🟡 REVIEW → ✅ PASS | Missing passport on first run; upload `passport_KYC-0059_Ivan_Lee.png` then re-run to resolve |
