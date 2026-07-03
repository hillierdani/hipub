import re
import json
import urllib.request
from urllib.parse import urlparse
from docx import Document
import fire
import pypdf

# Comprehensive list of trusted academic domains
LEGIT_ACADEMIC_DOMAINS = [
    'pubmed', 'ncbi.nlm.nih.gov', 'sciencedirect', 'biorxiv', 'nature.com',
    'elifesciences', 'science.org', 'frontiersin', 'academic.oup', 'pnas.org',
    'wiley', 'hal.science', 'openreview', 'arxiv', 'semanticscholar', 'cell.com',
    'jov.arvojournals', 'iovs.arvojournals', 'royalsocietypublishing', 'medrxiv'
]
import io
import re
import json
import urllib.request
import urllib.parse
import datetime
import html as html_lib


def handle_web_fallback(url):
    """Fallback method that reads live HTML webpage headers using browser mimicking
    to capture actual document metadata when registry API routes fail."""
    try:
        req_url = url
        # If pointing directly to a bioRxiv PDF, translate it back to the HTML landing page
        if url.lower().endswith('.pdf') and ('biorxiv.org' in url.lower() or 'medrxiv.org' in url.lower()):
            req_url = re.sub(r'\.full\.pdf$', '', url, flags=re.IGNORECASE).replace('.pdf', '')

        req = urllib.request.Request(req_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9'
        })

        with urllib.request.urlopen(req, timeout=5) as response:
            content_type = response.headers.get('Content-Type', '').lower()

            # Intercept binary streams to isolate structural asset data properties
            if 'application/pdf' in content_type or url.lower().endswith('.pdf'):
                try:
                    import pypdf
                    pdf_bytes = response.read()
                    with pypdf.PdfReader(io.BytesIO(pdf_bytes)) as reader:
                        meta = reader.metadata
                        title = meta.title.strip() if (meta and meta.title) else ""
                        author = [meta.author.strip()] if (meta and meta.author) else ["Unknown"]
                        if title and title.lower() not in ['blocked', '403 forbidden', 'not found']:
                            return author, "2026", title, "Journal PDF"
                except Exception:
                    pass
                html_content = ""  # Crash out gracefully to drop down to direct string manipulation
            else:
                html_content = response.read().decode('utf-8', errors='ignore')

            # Scrape Document Title via standard HighWire Academic or OpenGraph tags
            title_match = re.search(r'<meta\s+name="citation_title"\s+content="(.*?)"', html_content, re.IGNORECASE) or \
                          re.search(r'<meta\s+property="og:title"\s+content="(.*?)"', html_content, re.IGNORECASE) or \
                          re.search(r'<title>(.*?)</title>', html_content, re.DOTALL | re.IGNORECASE)

            title = title_match.group(1).strip() if title_match else ""
            title = re.sub(r'\s+', ' ', title)

            # Anti-Bot Security Block Detection Gate
            CHALLENGE_KEYWORDS = ['verifying your browser', 'cloudflare', 'attention required', 'robot check', 'captcha', '403 forbidden']
            if any(ck in title.lower() for ck in CHALLENGE_KEYWORDS):
                title = ""  # Nullify title string to force transition into string recovery backup

            if title and title.lower() not in ['blocked', '403 forbidden', 'not found', 'error']:
                # Scrape Document Authors
                author_matches = re.findall(r'<meta\s+name="citation_author"\s+content="(.*?)"', html_content, re.IGNORECASE)
                if not author_matches:
                    fallback_author = re.search(r'<meta\s+name="author"\s+content="(.*?)"', html_content, re.IGNORECASE)
                    author_matches = [fallback_author.group(1)] if fallback_author else []
                authors = [au.strip() for au in author_matches if au.strip()]
                if not authors: authors = ["Unknown"]

                # Scrape Publication Year
                year_match = re.search(r'<meta\s+name="citation_publication_date"\s+content="(\d{4})"', html_content, re.IGNORECASE) or \
                             re.search(r'<meta\s+name="citation_date"\s+content="(\d{4})"', html_content, re.IGNORECASE) or \
                             re.search(r'\b(19\d{2}|20\d{2})\b', html_content)
                year = year_match.group(1) if year_match else "2026"

                # Scrape Publishing Source / Journal Layout
                journal_match = re.search(r'<meta\s+name="citation_journal_title"\s+content="(.*?)"', html_content, re.IGNORECASE) or \
                                re.search(r'<meta\s+property="og:site_name"\s+content="(.*?)"', html_content, re.IGNORECASE)
                journal = journal_match.group(1).strip() if journal_match else ""

                if not journal:
                    domain_match = re.search(r'https?://(?:www\.)?([^/]+)', url)
                    journal = domain_match.group(1).capitalize() if domain_match else "Web Resource"
                return [html_lib.unescape(a) for a in authors], year, html_lib.unescape(title), html_lib.unescape(journal)

    except Exception:
        pass

    # Absolute bottom-tier string recovery layout if the URL connection times out completely
    if 'openreview.net' in url.lower():
        or_id = url.split('id=')[-1].split('&')[0]
        return ["OpenReview"], "2026", f"[OpenReview] {or_id}", "OpenReview Platform"

    domain_match = re.search(r'https?://(?:www\.)?([^/]+)', url)
    domain = domain_match.group(1).split('.')[0].capitalize() if domain_match else "Web"
    filename = url.split('/')[-1].split('?')[0].replace('.html', '').replace('.htm', '').replace('.pdf', '')
    title = f"[{domain}] {re.sub(r'[_+\-]+', ' ', filename).strip().capitalize()}"
    return [domain], "2026", title, "Web Resource"


def get_live_metadata(url):
    """Queries Crossref, Entrez, arXiv, and OpenReview registries via explicit
    architectural fallback paths and polite indexing headers."""
    filename_author, filename_year, filename_title = "Unknown", "2026", ""

    # 🔴 NCBI API Key Configuration (Successfully Integrated)
    NCBI_API_KEY = "af5c3517cfb808bc9c5809e468d9cc587708"
    ncbi_suffix = f"&api_key={NCBI_API_KEY}" if NCBI_API_KEY else ""

    try:
        # 1. Isolate administrative or tool domains to prevent useless queries
        ADMIN_DOMAINS = ['europa.eu', 'youtube.com', 'scribbr.com', 'grammar.com', 'languagetool.org', 'reescribirtextos.net', 'ahrefs.com', 'bio-techne.com', 'horizonteeuropa.es']
        if any(dom in url.lower() for dom in ADMIN_DOMAINS):
            return handle_web_fallback(url)

        doi = ""
        doi_query = ""

        # 2. General DOI Aggressive Extractor
        doi_match = re.search(r'(10\.\d{4,9}/[^\s,)\"\]\?]+)', url)
        if doi_match:
            doi = doi_match.group(1)
            for suffix in ['.full.pdf', '.full-text', '.full', '.pdf', '/full', '/pdf', '/abstract']:
                if doi.lower().endswith(suffix):
                    doi = doi[:-len(suffix)]
            # Fix: Strip preprint version updates (e.g., v1, v2) to prevent Crossref API 404s
            doi = re.sub(r'v\d+$', '', doi, flags=re.IGNORECASE)

        # Explicit Nature Domain Synthesis
        if not doi:
            nature_match = re.search(r'nature\.com/articles/([a-zA-Z0-9.\-_]+)', url, re.IGNORECASE)
            if nature_match:
                doi = f"10.1038/{nature_match.group(1)}"

        # 3. Handle Native Platform Registry Subdomain Mappings
        if not doi:
            # eLife Sub-Resolver
            elife_match = re.search(r'elifesciences\.org/(?:articles|reviewed-preprints)/(\d+)', url, re.IGNORECASE)
            if elife_match:
                doi = f"10.7554/eLife.{elife_match.group(1)}"

            # Robust Native OpenReview API Client
            openreview_match = re.search(r'openreview\.net/(?:forum|pdf)\?id=([\w\-]+)', url, re.IGNORECASE)
            if openreview_match:
                or_id = openreview_match.group(1)
                for api_version in ['api2', 'api']:
                    try:
                        or_api = f"https://{api_version}.openreview.net/notes?id={or_id}"
                        req = urllib.request.Request(or_api, headers={'User-Agent': 'Mozilla/5.0'})
                        with urllib.request.urlopen(req, timeout=4) as response:
                            or_data = json.loads(response.read().decode())
                            if or_data.get('notes'):
                                note = or_data['notes'][0]
                                content = note.get('content', {})
                                t_val = content.get('title', {})
                                title = t_val.get('value', 'Document') if isinstance(t_val, dict) else t_val
                                a_val = content.get('authors', {})
                                authors = a_val.get('value', ['OpenReview']) if isinstance(a_val, dict) else a_val
                                if not isinstance(authors, list): authors = [authors]
                                timestamp = note.get('cdate') or note.get('tcdate') or 1767222000000
                                year = str(datetime.datetime.fromtimestamp(timestamp / 1000).year)
                                return authors, year, title, "OpenReview"
                    except Exception:
                        pass

            # Native arXiv API Adapter
            arxiv_match = re.search(r'arxiv\.org/(?:pdf|abs)/(\d+\.\d+)', url, re.IGNORECASE)
            if arxiv_match:
                arxiv_id = arxiv_match.group(1)
                try:
                    arxiv_api = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
                    req = urllib.request.Request(arxiv_api, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=4) as response:
                        xml_data = response.read().decode()
                        entry_match = re.search(r'<entry>.*?</entry>', xml_data, re.DOTALL)
                        if entry_match:
                            entry = entry_match.group(0)
                            t_m = re.search(r'<title>(.*?)</title>', entry, re.DOTALL)
                            title = re.sub(r'\s+', ' ', t_m.group(1)).strip() if t_m else "arXiv Entry"
                            p_m = re.search(r'<published>(\d{4})', entry)
                            year = p_m.group(1) if p_m else "2026"
                            authors = re.findall(r'<name>(.*?)</name>', entry)
                            return (authors if authors else ["arXiv"]), year, title, "arXiv"
                except Exception:
                    pass
                doi = f"10.48550/arXiv.{arxiv_id}"

            # Entrez Resolver for PubMed Central (PMC) - Enhanced Mirror Extractor
            pmc_match = re.search(r'pmc\.ncbi\.nlm\.nih\.gov/articles/PMC(\d+)', url, re.IGNORECASE) or \
                        re.search(r'ncbi\.nlm\.nih\.gov/pmc/articles/PMC(\d+)', url, re.IGNORECASE) or \
                        re.search(r'[\/_]pmc(\d{5,8})', url, re.IGNORECASE)  # Catch third-party storage streams
            if pmc_match:
                pmcid = pmc_match.group(1)
                api_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pmc&id={pmcid}&retmode=json{ncbi_suffix}"
                req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=4) as response:
                    data = json.loads(response.read().decode())
                    info = data['result'][pmcid]
                    authors = [au['name'] for au in info.get('authors', [])] if info.get('authors') else ["Unknown"]
                    year_match = re.search(r'\b\d{4}\b', info.get('pubdate', '2026'))
                    year = year_match.group(0) if year_match else "2026"
                    title = info.get('title', 'Reference').strip('.')
                    return authors, year, title, info.get('source', 'PMC')

            # Entrez Resolver for Standard PubMed IDs (PMID)
            pubmed_match = re.search(r'pubmed\.ncbi\.nlm\.nih\.gov/(\d+)', url, re.IGNORECASE)
            if pubmed_match:
                pmid = pubmed_match.group(1)
                api_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={pmid}&retmode=json{ncbi_suffix}"
                req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=4) as response:
                    data = json.loads(response.read().decode())
                    info = data['result'][pmid]
                    authors = [au['name'] for au in info.get('authors', [])] if info.get('authors') else ["Unknown"]
                    year_match = re.search(r'\b\d{4}\b', info.get('pubdate', '2026'))
                    year = year_match.group(0) if year_match else "2026"
                    title = info.get('title', 'Reference').strip('.')
                    return authors, year, title, info.get('source', 'PubMed')

        # 4. Deep PDF Content Validation Stream
        if not doi and url.lower().endswith('.pdf'):
            try:
                import pypdf
                pdf_req = urllib.request.Request(url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/pdf'
                })
                with urllib.request.urlopen(pdf_req, timeout=6) as pdf_res:
                    pdf_bytes = pdf_res.read()
                    if pdf_bytes.startswith(b'%PDF'):
                        with pypdf.PdfReader(io.BytesIO(pdf_bytes)) as reader:
                            pdf_text = ""
                            for page_idx in range(min(2, len(reader.pages))):
                                pdf_text += reader.pages[page_idx].extract_text() or ""
                            pdf_doi_match = re.search(r'(10\.\d{4,9}/[^\s,)\"\]\?]+)', pdf_text)
                            if pdf_doi_match:
                                doi = re.sub(r'v\d+$', '', pdf_doi_match.group(1), flags=re.IGNORECASE)
            except Exception:
                pass

        # 5. Resolve Database Identifiers or Raw Strings for Query Generation
        if not doi:
            pii_match = re.search(r'/pii/([\w\d]{14,18})', url, re.IGNORECASE)
            if pii_match:
                # Fix: Wrap PII in literal quotes to force Crossref into exact match mode
                doi_query = f'"{pii_match.group(1)}"'
            elif 'escholarship.org' in url.lower():
                escholar_match = re.search(r'(?:item|content)/([\w\d]{8,10})', url)
                if escholar_match:
                    doi_query = f"escholarship {escholar_match.group(1)}"
            elif 'academic.oup.com' in url.lower():
                oup_match = re.search(r'/article/(\d+)', url) or re.search(r'/article/[^/]+/(\d+)', url)
                if oup_match: doi_query = f"Oxford OUP {oup_match.group(1)}"
            elif url.lower().endswith('.pdf'):
                filename = url.split('/')[-1].replace('.pdf', '')
                filename_title = re.sub(r'[_+\-]+', ' ', filename).strip()
                fn_match = re.search(r'^([A-Za-z]+)(\d{4})', filename)
                if fn_match:
                    filename_author, filename_year = fn_match.group(1), fn_match.group(2)
                query_text = re.sub(r'[_+\-]+', ' ', re.sub(r'(?<!^)(?=[A-Z])', ' ', filename)).strip()
                if len(query_text) > 8: doi_query = query_text

        # 6. Submit Metadata Request Packet directly to the Crossref Registry
        item = None
        polite_headers = {
            'User-Agent': 'AcademicMetadataParser/2.0 (mailto:gurkpeter@yahoo.com; ResilientBatchScript)',
            'Accept': 'application/json'
        }

        if doi:
            try:
                # Route A: Direct Metadata Object Fetch (Using safe='/' for paths)
                api_url = f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='/')}"
                req = urllib.request.Request(api_url, headers=polite_headers)
                with urllib.request.urlopen(req, timeout=5) as response:
                    item = json.loads(response.read().decode())['message']
            except Exception:
                # Route B: Downshift to a literal search query if direct fetch drops out
                doi_query = f'"{doi}"'

        if not item and doi_query:
            try:
                api_url = f"https://api.crossref.org/works?query={urllib.parse.quote(doi_query)}&rows=1"
                req = urllib.request.Request(api_url, headers=polite_headers)
                with urllib.request.urlopen(req, timeout=5) as response:
                    items = json.loads(response.read().decode())['message']['items']
                    if items: item = items[0]
            except Exception:
                pass

        if item:
            title = "Academic Reference"
            if item.get('title'):
                title = item['title'][0] if isinstance(item['title'], list) and item['title'] else str(item['title'])

            journal = ""
            if item.get('container-title'):
                journal = item['container-title'][0] if isinstance(item['container-title'], list) and item['container-title'] else str(item['container-title'])
            elif item.get('institution'):
                journal = item['institution'][0].get('name', '') if isinstance(item['institution'], list) else item['institution'].get('name', '')
            if not journal: journal = "Journal Resource"

            authors = []
            if item.get('author'):
                for au in item['author']:
                    family, given = au.get('family', ''), au.get('given', '')
                    authors.append(f"{family}, {given}" if family and given else family)
            authors = [au.strip() for au in authors if au and au.strip()]
            if not authors: authors = ["Unknown"]

            year = "2026"
            for date_field in ['published-print', 'published-online', 'created', 'issued']:
                if item.get(date_field) and item[date_field].get('date-parts') and item[date_field]['date-parts'][0]:
                    year = str(item[date_field]['date-parts'][0][0])
                    break
            return authors, year, title, journal

        if filename_author != "Unknown":
            return [filename_author], filename_year, filename_title, "Journal PDF"
        return handle_web_fallback(url)

    except Exception:
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