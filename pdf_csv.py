# import boto3
# import pandas as pd
# import os
# from dotenv import load_dotenv
# import fitz  # PyMuPDF

# load_dotenv()

# AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY")
# AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
# AWS_REGION = os.getenv("AWS_REGION")


# def textract_pdf_to_csv(pdf_path, csv_path):
#     """Extract table from PDF using AWS Textract and save to CSV.
#        Also calculates Textract OCR cost."""
    
#     # ----------- 1. COUNT PDF PAGES -------------
#     pdf_doc = fitz.open(pdf_path)
#     num_pages = len(pdf_doc)
#     pdf_doc.close()

#     # AWS Textract Table cost: $1.50 per 1000 pages = $0.0015 per page
#     cost_per_page_usd = 0.0015
#     total_cost_usd = num_pages * cost_per_page_usd
#     total_cost_inr = total_cost_usd * 86   # approx 1 USD = ₹86

#     print("------------------------------------------------")
#     print(f"📄 PDF Pages: {num_pages}")
#     print(f"💰 Estimated Textract Cost (USD): ${total_cost_usd:.4f}")
#     print(f"💰 Estimated Textract Cost (INR): ₹{total_cost_inr:.2f}")
#     print("------------------------------------------------")

#     # ------------ 2. CALL TEXTRACT ----------------
#     textract = boto3.client(
#         "textract",
#         aws_access_key_id=AWS_ACCESS_KEY_ID,
#         aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
#         region_name=AWS_REGION,
#     )

#     with open(pdf_path, "rb") as f:
#         pdf_bytes = f.read()

#     response = textract.analyze_document(
#         Document={"Bytes": pdf_bytes},
#         FeatureTypes=["TABLES"]
#     )

#     blocks = response["Blocks"]
#     cell_map = {}
#     max_row, max_col = 0, 0

#     for block in blocks:
#         if block["BlockType"] == "CELL":
#             row, col = block["RowIndex"], block["ColumnIndex"]
#             max_row = max(max_row, row)
#             max_col = max(max_col, col)

#             text = ""
#             if "Relationships" in block:
#                 for rel in block["Relationships"]:
#                     if rel["Type"] == "CHILD":
#                         for cid in rel["Ids"]:
#                             child = next((b for b in blocks if b["Id"] == cid), None)
#                             if child and child["BlockType"] == "WORD":
#                                 text += child["Text"] + " "
#             cell_map[(row, col)] = text.strip()

#     # ----------- 3. BUILD TABLE ----------------
#     table = []
#     for r in range(1, max_row + 1):
#         row_data = []
#         for c in range(1, max_col + 1):
#             row_data.append(cell_map.get((r, c), ""))
#         table.append(row_data)

#     df = pd.DataFrame(table)
#     df.replace("", pd.NA, inplace=True)
#     df.dropna(how="all", inplace=True)
#     df.reset_index(drop=True, inplace=True)

#     # ----------- 4. SAVE CSV -------------------
#     df.to_csv(csv_path, index=False)
#     print(f"✅ CSV created successfully: {csv_path}")

#     # Return Data + Cost
#     return {
#         "dataframe": df,
#         "pages": num_pages,
#         "cost_usd": total_cost_usd,
#         "cost_inr": total_cost_inr
#     }




# # -------------------------
# # Example usage
# # -------------------------

# pdf_path = "C:\\Users\\infyz\\Downloads\\1990\\1990 Averages ETo Data(jan-dec).pdf"
# csv_path = "1990_ETo_Averages.csv"

# result = textract_pdf_to_csv(pdf_path, csv_path)
# print(result["cost_usd"])  # print cost in USD
# print(result["cost_inr"])  # print cost in INR


import os
import fitz
import pandas as pd
from dotenv import load_dotenv
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential

load_dotenv()

AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_CONTAINER_NAME = "bothradocuments"
AZURE_DIR = "rake_weighment_documents"

FORM_RECOGNIZER_ENDPOINT = os.getenv("AZURE_FORM_RECOGNIZER_ENDPOINT")
FORM_RECOGNIZER_KEY = os.getenv("AZURE_FORM_RECOGNIZER_KEY")


# ---------- COUNT PDF PAGES ----------
def count_pdf_pages(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        pages = len(doc)
        doc.close()
        return pages
    except:
        return 0


# ---------- EXTRACT TABLE USING AZURE ----------
def extract_table_azure(pdf_path, client):
    with open(pdf_path, "rb") as f:
        poller = client.begin_analyze_document("prebuilt-layout", document=f)
    result = poller.result()

    tables = []
    for table in result.tables:
        data = []
        for row in table.cells:
            # build row matrix
            pass

        # Build dataframe from Azure table
        rows = max(cell.row_index for cell in table.cells) + 1
        cols = max(cell.column_index for cell in table.cells) + 1

        table_matrix = [["" for _ in range(cols)] for _ in range(rows)]

        for cell in table.cells:
            table_matrix[cell.row_index][cell.column_index] = cell.content

        df = pd.DataFrame(table_matrix)
        tables.append(df)

    return tables


# ---------- PROCESS FOLDER ----------
def process_folder_azure(input_folder, output_csv):

    client = DocumentAnalysisClient(
        endpoint=FORM_RECOGNIZER_ENDPOINT,
        credential=AzureKeyCredential(FORM_RECOGNIZER_KEY)
    )

    all_dataframes = []
    total_pages = 0

    pdf_files = [f for f in os.listdir(input_folder) if f.lower().endswith(".pdf")]
    print(f"📁 Found {len(pdf_files)} PDF files")

    for idx, filename in enumerate(pdf_files, 1):
        pdf_path = os.path.join(input_folder, filename)
        print(f"\n🔄 Processing {idx}/{len(pdf_files)} → {filename}")

        pages = count_pdf_pages(pdf_path)
        total_pages += pages

        try:
            tables = extract_table_azure(pdf_path, client)

            # Merge tables in this PDF
            pdf_df = pd.concat(tables, ignore_index=True)
            pdf_df["source_file"] = filename

            all_dataframes.append(pdf_df)

            print(f"   ✅ Extracted {len(pdf_df)} rows")

        except Exception as e:
            print(f"   ❌ Failed: {e}")

    # ---------- COMBINE ALL ----------
    if all_dataframes:
        final_df = pd.concat(all_dataframes, ignore_index=True)
        final_df.to_csv(output_csv, index=False)
        print(f"\n🎉 FINAL CSV CREATED: {output_csv}")
    else:
        print("❌ No tables extracted.")
        return

    # ---------- COST ----------
    cost_per_page_usd = 0.01   # Azure Layout cost
    total_cost_usd = total_pages * cost_per_page_usd
    total_cost_inr = total_cost_usd * 86

    print("\n--------------------------------------------------")
    print(f"📄 Total PDFs processed : {len(pdf_files)}")
    print(f"📄 Total pages scanned  : {total_pages}")
    print(f"💰 Azure OCR Cost (USD): ${total_cost_usd:.4f}")
    print(f"💰 Azure OCR Cost (INR): ₹{total_cost_inr:.2f}")
    print("--------------------------------------------------")


# ---------- RUN SCRIPT ----------

input_folder = r"DATA"       # folder with 400+ PDFs
output_csv = r"final_eto_output_azure.csv"

process_folder_azure(input_folder, output_csv)
