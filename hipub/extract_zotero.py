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

import urllib.parse


def handle_web_fallback(url):
    """Generates clean, structured metadata descriptions out of web resources or raw URLs."""
    try:
        # Try a swift header scrape for native page titles (handles YouTube, Scribbr, etc.)
        if not url.lower().endswith(('.pdf', '.rtf', '.docx')):
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as response:
                html = response.read().decode('utf-8', errors='ignore')
                title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
                if title_match:
                    page_title = re.sub(r'\s+', ' ', title_match.group(1).strip())
                    if len(page_title) > 4:
                        domain = urlparse(url).netloc.replace('www.', '').split('.')[0].capitalize()
                        return [domain], "2026", page_title, ""
    except Exception:
        pass

    # Fallback to intelligent URL file name parsing if the page blocks scraping
    parsed = urlparse(url)
    domain = parsed.netloc.replace('www.', '').split('.')[0].capitalize()
    path_segments = [s for s in parsed.path.split('/') if s]
    if path_segments:
        last_seg = path_segments[-1]
        last_seg = re.sub(r'\.(pdf|html|htm|rtf|aspx)$', '', last_seg, flags=re.IGNORECASE)
        title_text = re.sub(r'[_+\-]+', ' ', last_seg).strip().title()
        if len(title_text) > 4:
            return [domain], "2026", f"[{domain}] {title_text}", ""
    return [domain], "2026", f"[{domain}] Web Resource", ""


def get_live_metadata(url):
    """Queries Crossref and Entrez registries via explicit DOI parsing,
    identifier tracking, and filename semantic querying."""
    # Initialize variables for structural filename parsing fallbacks
    filename_author, filename_year, filename_title = "Unknown", "2026", ""

    try:
        # 1. Isolate administrative or service domains to bypass API delays
        ADMIN_DOMAINS = ['europa.eu', 'youtube.com', 'scribbr.com', 'grammar.com', 'languagetool.org', 'reescribirtextos.net', 'ahrefs.com', 'bio-techne.com', 'horizonteeuropa.es']
        if any(dom in url.lower() for dom in ADMIN_DOMAINS):
            return handle_web_fallback(url)

        doi = ""
        doi_query = ""

        # 2. General DOI Aggressive Extractor (Captures Wiley, PNAS, Science, Royal Society, bioRxiv codes)
        doi_match = re.search(r'(10\.\d{4,9}/[^\s,)\"\]\?]+)', url)
        if doi_match:
            doi = doi_match.group(1)
            # Remove typical asset trailing noise from the extracted DOI string
            for suffix in ['.full.pdf', '.full-text', '.full', '.pdf', '/full', '/pdf', '/abstract']:
                if doi.lower().endswith(suffix):
                    doi = doi[:-len(suffix)]
            doi = re.sub(r'v\d+$', '', doi, flags=re.IGNORECASE)

        # 3. Handle Platform Subdomain Mappings (eLife, arXiv, PMC)
        if not doi:
            elife_match = re.search(r'elifesciences\.org/articles/(\d+)', url, re.IGNORECASE)
            if elife_match:
                doi = f"10.7554/eLife.{elife_match.group(1)}"

            arxiv_match = re.search(r'arxiv\.org/(?:pdf|abs)/(\d+\.\d+)', url, re.IGNORECASE)
            if arxiv_match:
                doi = f"10.48550/arXiv.{arxiv_match.group(1)}"

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
                    year = re.search(r'\b\d{4}\b', info.get('pubdate', '2026')).group(0)
                    return authors, year, info.get('title', 'Reference'), info.get('source', 'PMC')

        # 4. Resolve Database Identifiers or Raw Filenames for Search
        if not doi:
            pii_match = re.search(r'/pii/([\w\d]{14,18})', url, re.IGNORECASE)
            if pii_match:
                doi_query = pii_match.group(1)
            elif 'academic.oup.com' in url.lower():
                oup_match = re.search(r'/article/(\d+)', url) or re.search(r'/article/[^/]+/(\d+)', url)
                if oup_match:
                    doi_query = f"Oxford OUP {oup_match.group(1)}"
            elif 'arvojournals.org' in url.lower():
                arvo_match = re.search(r'articleid=(\d+)', url, re.IGNORECASE)
                if arvo_match:
                    doi_query = f"ARVO article {arvo_match.group(1)}"
            elif url.lower().endswith('.pdf'):
                # Extract file name words from raw university library paths
                filename = url.split('/')[-1].replace('.pdf', '')
                filename_title = re.sub(r'[_+\-]+', ' ', filename).strip()

                # Pre-extract structured author/year formatting rules (e.g., Namima2025_JNeurosci)
                fn_match = re.search(r'^([A-Za-z]+)(\d{4})', filename)
                if fn_match:
                    filename_author = fn_match.group(1)
                    filename_year = fn_match.group(2)

                query_text = re.sub(r'(?<!^)(?=[A-Z])', ' ', filename)  # Split camelCase strings
                query_text = re.sub(r'[_+\-]+', ' ', query_text).strip()
                if len(query_text) > 8:
                    doi_query = query_text

        # 5. Submit Query Packet directly to the Crossref Registry
        final_target = doi if doi else doi_query
        if final_target:
            api_param = f"works/{final_target}" if doi else f"works?query={urllib.parse.quote(final_target)}&rows=1"
            api_url = f"https://api.crossref.org/{api_param}"
            req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=4) as response:
                data = json.loads(response.read().decode())

                if 'items' in data['message']:
                    if not data['message']['items']:
                        raise ValueError()
                    item = data['message']['items'][0]
                else:
                    item = data['message']

                title = item.get('title', ['Academic Reference'])[0]
                journal = item['container-title'][0] if item.get('container-title') else ""
                authors = []
                if item.get('author'):
                    for au in item['author']:
                        family, given = au.get('family', ''), au.get('given', '')
                        authors.append(f"{family}, {given}" if family and given else family)

                # Sanitize empty string array objects to completely neutralize the split index crash
                authors = [au.strip() for au in authors if au and au.strip()]
                if not authors:
                    if filename_author != "Unknown":
                        return [filename_author], filename_year, filename_title, "Journal PDF"
                    authors = ["Unknown"]

                year = "2026"
                for date_field in ['published-print', 'published-online', 'created']:
                    if item.get(date_field) and item[date_field].get('date-parts'):
                        year = str(item[date_field]['date-parts'][0][0])
                        break
                return authors, year, title, journal

        # 6. Primary Safety Catch: If no search query worked but filename data is clean
        if filename_author != "Unknown":
            return [filename_author], filename_year, filename_title, "Journal PDF"
        return handle_web_fallback(url)

    except Exception:
        # 7. Emergency Exception Wrapper Fallback Strategy
        if filename_author != "Unknown":
            return [filename_author], filename_year, filename_title, "Journal PDF"
        return handle_web_fallback(url)


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
    """Parses a single scannable string for Word document in-text bracket injections securely."""
    if not authors or not isinstance(authors, list):
        return fallback

    # Filter out empty strings or padding whitespace
    clean_authors = [a.strip() for a in authors if a and a.strip()]
    if not clean_authors:
        return fallback

    first_author = clean_authors[0]
    tokens = first_author.split(',') if ',' in first_author else first_author.split()
    lastname = tokens[0].strip() if tokens else fallback

    if len(clean_authors) > 1:
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