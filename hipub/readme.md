# extract_zotero.py - Reference Resolution & Citation Processor

## Overview

A Python script that scans a Word document (`.docx`) for URLs in references, resolves academic metadata from multiple registry APIs (Crossref, PubMed, arXiv, PMC, OpenReview), and outputs:
- A marked document (`.docx`) with citation placeholders like `{Smith, 2024}`
- An RIS file (`.ris`) for importing into Zotero

---

## Dependencies

```
docx, fire, pypdf, requests, urllib (stdlib)
```

## Usage

### Quick Start

```bash
python extract_zotero.py paper.docx
```

Or provide full output paths explicitly:

```bash
python extract_zotero.py paper.docx --output_docx=my_marked.docx --output_ris=my_refs.ris
```

### Argument Reference

| Argument | Default | Description |
|----------|---------|-------------|
| `input_docx` | (required) | Input Word document to process |
| `output_docx` | `marked_document.docx` | Output marked document |
| `output_ris` | `zotero_import.ris` | Output RIS bibliography file |

### PyCharm Configuration

To specify arguments in PyCharm, go to **Run -> Edit Configurations** and add your file path in the **Script Parameters** box.

---

## What the Script Does

### Step 1: Reference Extraction

The script parses the document paragraphs and extracts all URLs referenced in:

1. **Marked citations** — explicit `[n] https://...` patterns  
2. **Numbered lists** — bullets numbered by Word's List Number style  
3. **Plain paragraphs** — implicit numbered references  

Each extracted URL is assigned a reference number and mapped to a dictionary (`ref_num_to_url`).

### Step 2: BioRxiv Version Optimization

If the references contain multiple versions of the same bioRxiv preprint (e.g., `v1`, `v2`), the script identifies the latest version and remaps all older URL markers to point to the latest version.

### Step 3: Metadata Resolution

For each unique URL, the script calls `get_live_metadata()` which attempts (in priority order):

| Route | Target |
|-------|--------|
| **Crossref DOI API** | Standard DOI-based papers |
| **Entrez/PMC API** | PubMed Central articles (PMCID) |
| **Entrez/PubMed API** | Standard PubMed IDs (PMID) |
| **arXiv API** | Preprints from arXiv |
| **OpenReview API** | Conference submissions |
| **eLife resolver** | Articles from elifesciences.org |
| **Nature synthesiser** | Articles from nature.com/articles/* |
| **Crossref query** | Text-based fallback searches |
| **Web scraping** | Fallback — grabs page HTML meta tags (citation_title, citation_author, etc.) |

The script includes a whitelist of trusted academic domains (pubmed, sciencedirect, nature.com, biorxiv, frontiersin, etc.) and a blacklist of non-academic domains (YouTube, Wikipedia, Reddit, medium, news sites, etc.) that are excluded from results.

#### API Key Requirement

The script uses a hardcoded NCBI API key for PubMed/PMC queries. To obtain your own API key from NCBI, you need to create an account and generate one.

### Step 4: Duplicate Resolution

If multiple URLs resolve to the same paper title, the script merges them — keeping the metadata entry with the most complete journal information and removing duplicates from the registry.

### Step 5: Document Annotation

The script rewrites all `[n]` in-text citation markers in the document to `{DisplayAuthor, Year}` format (e.g., `{Smith et al., 2024}`). The "display" author is the cleaned primary surname followed by "et al." if multiple authors are detected.

### Step 6: RIS Bibliography Export

A valid RIS file is written containing one record per resolved reference, with standard fields: `TY` (type), `AU` (authors), `PY` (year), `TI` (title), `JO` (journal), and `UR` (URL).

---

## Post-Processing Steps

### Step 1: Import the RIS into Zotero

1. Open **Zotero**.
2. Go to **File > Import > Select a file > Choose the .ris file** you generated.
3. Zotero will import these items.
4. Imported references should go to a new collection. If you see many unresolved links or weird items, you can remove them (Cmd+Option+Backspace can move items into trash). This way you don't clutter your Zotero database.

### Step 2: Convert the Word Doc to RTF

1. Open the newly created `marked_document.docx` in **Microsoft Word**.
2. Go to **File > Save As**.
3. In the file format dropdown, select **Rich Text Format (.rtf)** and save it.

### Step 3: Run Zotero RTF Scan

1. In Zotero, click **Tools** in the top menu bar and select **RTF Scan**.
2. For the **Input File**, select the `.rtf` file you just saved.
3. Choose a name for the **Output File** (e.g., `final_citations.rtf`).
4. Click **Next**. Zotero will match `{Smith, 2024}` tags with the imported item and convert them into live database links (Ref1, Ref2, etc.).

---

## Supported URL Types

The script can resolve metadata from:

- PubMed Central (PMC) IDs
- Standard PubMed (PMID) references
- Crossref DOI links (all publishers via DOI resolution)
- arXiv preprints (pdf & abs)
- OpenReview conference submissions
- bioRxiv preprints (with version handling)
- Nature published articles
- eLife articles
- Oxford University Press (OUP) links
- Direct PDF files (DOI extraction from embedded metadata)

Administrative, Wikipedia, news, and non-scientific URLs are filtered out during processing.

---

## Notes

- The script returns `"2026"` as a default year when metadata cannot be resolved.
- Web-scraping attempts have a 5–10 second timeout to prevent hangs.
- The `is_academic_record()` filter ensures only legitimate scientific papers make it into the final output.
