import re
import json
import urllib.request
from urllib.parse import urlparse
from docx import Document
import fire

# Comprehensive list of trusted academic domains
LEGIT_ACADEMIC_DOMAINS = [
    'pubmed', 'ncbi.nlm.nih.gov', 'sciencedirect', 'biorxiv', 'nature.com',
    'elifesciences', 'science.org', 'frontiersin', 'academic.oup', 'pnas.org',
    'wiley', 'hal.science', 'openreview', 'arxiv', 'semanticscholar', 'cell.com',
    'jov.arvojournals', 'iovs.arvojournals', 'royalsocietypublishing', 'medrxiv'
]

import urllib.parse


def get_live_metadata(url):
    """Advanced metadata parser that resolves structured patterns, scrapes meta tags,
    queries filenames semantically via Crossref, and captures webpage title layers."""
    try:
        scrape_url = url
        doi = ""
        doi_query = ""

        # --- Step A: Structural Transpositions & Cleanups ---
        if 'openreview.net/pdf' in url.lower():
            scrape_url = url.replace('/pdf?', '/forum?')
        elif 'hal.science' in url.lower():
            scrape_url = re.sub(r'/file/.*$', '', scrape_url)
            scrape_url = re.sub(r'/document/?$', '', scrape_url)

        # Extract explicit eLife article references
        elife_match = re.search(r'elifesciences\.org/articles/(\d+)', url, re.IGNORECASE)
        if elife_match:
            doi = f"10.7554/eLife.{elife_match.group(1)}"

        # Extract explicit arXiv tracking tokens
        arxiv_match = re.search(r'arxiv\.org/(?:pdf|abs)/(\d+\.\d+)', url, re.IGNORECASE)
        if arxiv_match:
            doi = f"10.48550/arXiv.{arxiv_match.group(1)}"

        # Isolate ScienceDirect PII Identifiers to resolve via Crossref lookup query
        pii_match = re.search(r'/pii/([\w\d]{14,18})', url, re.IGNORECASE)
        if pii_match:
            doi_query = pii_match.group(1)

        # --- Step B: Traditional PMC / PubMed Query Routing ---
        if not doi and not doi_query:
            pmc_match = re.search(r'pmc\.ncbi\.nlm\.nih\.gov/articles/PMC(\d+)', url, re.IGNORECASE) or \
                        re.search(r'ncbi\.nlm\.nih\.gov/pmc/articles/PMC(\d+)', url, re.IGNORECASE)
            if pmc_match:
                pmcid = pmc_match.group(1)
                api_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pmc&id={pmcid}&retmode=json"
                req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=4) as response:
                    data = json.loads(response.read().decode())
                    info = data['result'][pmcid]
                    authors = [au['name'] for au in info.get('authors', [])] if info.get('authors') else ["Unknown"]
                    return authors, re.search(r'\b\d{4}\b', info.get('pubdate', '')).group(0), info.get('title', 'Reference'), info.get('source', 'PMC')

            pubmed_match = re.search(r'pubmed\.ncbi\.nlm\.nih\.gov/(\d+)', url, re.IGNORECASE)
            if pubmed_match:
                pmid = pubmed_match.group(1)
                api_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={pmid}&retmode=json"
                req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=4) as response:
                    data = json.loads(response.read().decode())
                    info = data['result'][pmid]
                    authors = [au['name'] for au in info.get('authors', [])] if info.get('authors') else ["Unknown"]
                    return authors, re.search(r'\b\d{4}\b', info.get('pubdate', '')).group(0), info.get('title', 'Reference'), info.get('source', '')

        # --- Step C: HTML Header Scraper Fallback & Web Title Captures ---
        if not doi and not doi_query and not url.lower().endswith('.pdf'):
            try:
                req = urllib.request.Request(scrape_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=4) as response:
                    html = response.read().decode('utf-8', errors='ignore')
                    meta_match = re.search(r'<meta[^>]*name=["\'](?:citation_doi|dc\.identifier|dc\.doi)["\'][^>]*content=["\'](10\.\d{4,9}/[^"\']+)["\']', html, re.IGNORECASE) or \
                                 re.search(r'<meta[^>]*content=["\'](10\.\d{4,9}/[^"\']+)["\'][^>]*name=["\'](?:citation_doi|dc\.identifier|dc\.doi)["\']', html, re.IGNORECASE)
                    if meta_match:
                        doi = meta_match.group(1)
                    else:
                        # Fallback for administrative or non-document web resources (ERC, YouTube, etc.)
                        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
                        if title_match:
                            page_title = re.sub(r'\s+', ' ', title_match.group(1).strip())
                            year_match = re.search(r'\b(202\d|201\d)\b', scrape_url)
                            year = year_match.group(0) if year_match else "2026"
                            domain_name = urlparse(scrape_url).netloc.replace('www.', '').split('.')[0].capitalize()
                            return [domain_name], year, page_title, ""  # Empty journal signifies it's a structural web document
            except Exception:
                pass

        # --- Step D: Lab Publication PDF Metadata Query Fallback ---
        if not doi and not doi_query and url.lower().endswith('.pdf'):
            filename = url.split('/')[-1].replace('.pdf', '')
            query_text = re.sub(r'[_+\-]+', ' ', filename).strip()
            if len(query_text) > 10:
                doi_query = query_text

        # --- Step E: Execution Engine via Crossref Metadata Store ---
        final_query = doi if doi else doi_query
        if final_query:
            api_param = f"works/{final_query}" if doi else f"works?query={urllib.parse.quote(final_query)}&rows=1"
            api_url = f"https://api.crossref.org/{api_param}"
            req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=4) as response:
                data = json.loads(response.read().decode())
                item = data['message']['items'][0] if 'items' in data['message'] else data['message']

                title = item.get('title', ['Academic Reference'])[0]
                journal = item['container-title'][0] if item.get('container-title') else ""
                authors = []
                if item.get('author'):
                    for au in item['author']:
                        family, given = au.get('family', ''), au.get('given', '')
                        authors.append(f"{family}, {given}" if family and given else family)
                if not authors:
                    authors = ["Unknown"]

                year = "2026"
                for date_field in ['published-print', 'published-online', 'created']:
                    if item.get(date_field) and item[date_field].get('date-parts'):
                        year = str(item[date_field]['date-parts'][0][0])
                        break
                return authors, year, title, journal
    except Exception:
        pass
    return None


def parse_fallback_meta(url, ref_num):
    """Generates unique fallback metadata tags for unparsed or non-academic links."""
    try:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.replace('www.', '')
        domain_name = domain.split('.')[0].capitalize()
    except Exception:
        domain_name = "Weblink"

    author = f"{domain_name}_{ref_num}"
    year_match = re.search(r'\b(19[5-9]\d|20[0-2]\d)\b', url)
    year = year_match.group(0) if year_match else "2026"
    return [author], year, url


def get_display_author(authors, fallback="Unknown"):
    """Parses a single scannable string for Word document in-text bracket injections."""
    if not authors:
        return fallback
    first_author = authors[0]
    # Handle "Family, Given" splitting vs "Family GI" splitting
    lastname = first_author.split(',')[0].strip() if ',' in first_author else first_author.split()[0].strip()

    if len(authors) > 1:
        return f"{lastname} et al."
    return lastname


def convert(input_docx, output_docx="marked_document.docx", output_ris="zotero_import.ris"):
    """
    Scans document references, captures text lists and native lists,
    normalizes academic metadata with full author profiles, and creates Zotero packages.
    """
    doc = Document(input_docx)

    ref_num_to_url = {}
    url_pattern = re.compile(r'https?://\S+')
    text_ref_pattern = re.compile(r'(\d+)\s*[\.\s\t)\]\-:]+\s*(https?://\S+)')

    native_list_counter = 1

    print("🔍 Step 1: Scanning document structure for references (Text & Native Lists)...")
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        url_match = url_pattern.search(text)
        if not url_match:
            continue

        url = url_match.group(0).rstrip('.,] ) ')

        # Strategy A: Plain text numbering configurations
        text_match = text_ref_pattern.search(text)
        if text_match:
            ref_num = text_match.group(1)
            ref_num_to_url[ref_num] = url
            continue

        # Strategy B: Native Word Ordered List Elements
        is_native_list = bool(para._element.xpath('./w:pPr/w:numPr')) or para.style.name.startswith('List Number')
        if is_native_list:
            ref_num = str(native_list_counter)
            ref_num_to_url[ref_num] = url
            native_list_counter += 1
            continue

        # Strategy C: Raw URLs floating inside strings
        num_fallback = re.search(r'\b(\d+)\b', text)
        if num_fallback:
            ref_num = num_fallback.group(1)
        else:
            ref_num = str(native_list_counter)
            native_list_counter += 1
        ref_num_to_url[ref_num] = url

    if not ref_num_to_url:
        print("❌ Error: Could not extract references containing metadata targets.")
        return

    unique_urls = list(set(ref_num_to_url.values()))
    print(f"📊 Extracted {len(ref_num_to_url)} total citations mapping to {len(unique_urls)} unique web assets.")

    print("\n🌐 Step 2: Fetching deep metadata and building reference tracking registry...")
    url_metadata_registry = {}
    unresolved_links = []

    for url in unique_urls:
        sample_ref_num = [k for k, v in ref_num_to_url.items() if v == url][0]

        # Route everything directly through our adaptive pipeline
        meta = get_live_metadata(url)

        if meta:
            authors, year, title, journal = meta
            display_name = get_display_author(authors)

            # If a structural journal string exists, map as publication, else save as a web bookmark
            entry_type = 'JOUR' if journal else 'ELEC'

            url_metadata_registry[url] = {
                'type': entry_type, 'authors': authors, 'display': display_name, 'year': year, 'title': title, 'journal': journal
            }
            if entry_type == 'JOUR':
                print(f"  ✅ Academic Asset Found: {display_name} ({year})")
            else:
                print(f"  🔗 Webpage Registered cleanly: {display_name} -> {title[:40]}...")
        else:
            authors, year, title = parse_fallback_meta(url, sample_ref_num)
            display_name = get_display_author(authors)
            url_metadata_registry[url] = {
                'type': 'ELEC', 'authors': authors, 'display': display_name, 'year': year, 'title': title, 'journal': ''
            }
            unresolved_links.append(url)
            print(f"  ❌ Unresolved Asset Flagged: {display_name}")

    print("\n📝 Step 3: Upgrading document in-text bracket components...")
    inline_pattern = re.compile(r'\[(\d+)\]')

    for para in doc.paragraphs:
        matches = inline_pattern.findall(para.text)
        if matches:
            new_text = para.text
            for ref_num in matches:
                if ref_num in ref_num_to_url:
                    url = ref_num_to_url[ref_num]
                    meta = url_metadata_registry[url]
                    # Upgrades [47] -> {Smith et al., 2026}
                    new_text = new_text.replace(f"[{ref_num}]", f"{{{meta['display']}, {meta['year']}}}")
            para.text = new_text

    doc.save(output_docx)
    print(f"💾 Structural document modifications written to: {output_docx}")

    print("\n📁 Step 4: Formatting and outputting deep-indexed Zotero RIS database...")
    with open(output_ris, 'w', encoding='utf-8') as ris_file:
        for url, data in url_metadata_registry.items():
            ris_file.write(f"TY  - {data['type']}\n")

            # Formats an independent AU tag line for every single discovered author
            for author in data['authors']:
                ris_file.write(f"AU  - {author}\n")

            ris_file.write(f"PY  - {data['year']}\n")
            ris_file.write(f"TI  - {data['title']}\n")
            if data['journal']:
                ris_file.write(f"JO  - {data['journal']}\n")
            ris_file.write(f"UR  - {url}\n")
            ris_file.write("ER  - \n\n")

    print(f"✅ Success! Run Zotero's RTF Scan over your marked files.")

    # <-- ADD THIS BLOCK AT THE VERY END OF YOUR CONVERT FUNCTION
    print("\n" + "=" * 50)
    print("⚠️  DEBUG: UNRESOLVED LINKS (WEBPAGE REGISTERED)")
    print("=" * 50)
    for link in unresolved_links:
        print(link)
    print("=" * 50)


if __name__ == '__main__':
    fire.Fire(convert)