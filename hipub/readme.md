The Step-by-Step Conversion Process

```python zotero_prep.py paper.docx```

or provide the full path to the docx file in PyCharm's Run -> Edit configurations -> Script Parameters box.

You may need to create a PMC/NCBI account and generate your API key.

The script tries to resolve as many as possible scientific journal references. Performs de-duplication and discards references that are clearly not scientific.

Once the script completes, follow these steps to turn those text brackets into live Zotero items:

# Step 1: Import the RIS into Zotero
1. Open Zotero.

2. Go to File > Import > select A file > choose zotero_import.ris.

3. Zotero will import these items. Some references will have weird creators: those are not scientific journal links.

4. Imported references should go to a new collection. If you see many unresolved links or weird items, you can remove new items cmd-option-backspace can move these into trash. This way you don't clutter your zotero database.
# Step 2: Convert the Word Doc to RTF
1. Open the newly created marked_document.docx in Microsoft Word.
2. Go to File > Save As.
3. In the file format dropdown, select Rich Text Format (.rtf) and save it.

# Step 3: Run Zotero RTF Scan
1. In Zotero, click Tools in the top menu bar and select RTF Scan.
2. For the Input File, select the .rtf file you just saved.
3. Choose a name for the Output File (e.g., final_citations.rtf).
4. Click Next. Zotero will instantly read {Ref298, 2026}, match it with the item you imported in Step 1, and convert it into a live database code.

# Step 4: Fetch Real Metadata & Clean Up
1. Open your brand new final_citations.rtf file in Word and Save As a normal .docx file. Your citations are now fully functional Zotero elements!
2. Go back to your Zotero Library, select the newly imported items, right-click them, and choose Find Available Metadata (or use Zotero's magic wand to pull the official PubMed details over the top of the URLs).
3. Click Refresh inside the Word Zotero plugin tab. The fake tags like (Ref298, 2026) will instantly update themselves to the true author names and dates (e.g., (Smith, 2024)), generating a perfect bibliography at the bottom of your document.