import re
import json
import urllib.request
from urllib.parse import urlparse
from docx import Document
import fire
import pypdf
import re
import requests

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


def optimize_biorxiv_versions(ref_num_to_url):
    """
    Scans reference mapping for bioRxiv URLs. If multiple versions of the same
    paper are cited (e.g., v1 and v2), it identifies the latest version,
    and remaps all matching documents to ensure the latest version is used.
    """
    base_to_max_ver = {}

    # Pass 1: Trace all bioRxiv links and extract maximum version numbers
    for ref_num, url in ref_num_to_url.items():
        if 'biorxiv.org' in url.lower():
            match = re.match(r'(https?://(?:www\.)?biorxiv\.org/content/10\.1101/[\d\.]+)(v\d+)?', url)
            if match:
                base_url = match.group(1)
                ver_str = match.group(2) if match.group(2) else "v1"
                ver_num = int(ver_str[1:])

                if base_url not in base_to_max_ver or ver_num > base_to_max_ver[base_url]['ver_num']:
                    base_to_max_ver[base_url] = {
                        'ver_num': ver_num,
                        'ver_str': ver_str,
                        'full_url': f"{base_url}{ver_str}" if match.group(2) else url
                    }

    # Pass 2: Remap references pointing to older versions to the latest version discovered
    for ref_num, url in list(ref_num_to_url.items()):
        if 'biorxiv.org' in url.lower():
            match = re.match(r'(https?://(?:www\.)?biorxiv\.org/content/10\.1101/[\d\.]+)(v\d+)?', url)
            if match:
                base_url = match.group(1)
                if base_url in base_to_max_ver:
                    latest_url = base_to_max_ver[base_url]['full_url']
                    if url != latest_url:
                        print(f"🔄 Remapping bioRxiv marker [{ref_num}] from older version ({match.group(2) or 'v1'}) -> latest ({base_to_max_ver[base_url]['ver_str']})")
                        ref_num_to_url[ref_num] = latest_url

    return ref_num_to_url


def get_display_author(authors, fallback="Unknown"):
    """
    Extracts the clean primary surname and appends 'et al.' if multiple authors exist.
    Strictly strips out trailing or isolated initials to prevent 'Lastname X et al.'
    """
    if not authors or not isinstance(authors, list):
        return fallback
    clean_authors = [a.strip() for a in authors if a and a.strip()]
    if not clean_authors:
        return fallback

    first_author = clean_authors[0]

    # Handle "Family, Given" layout
    if ',' in first_author:
        lastname = first_author.split(',')[0].strip()
    else:
        # Handle "Given Family" or "Family Initial" structures
        tokens = first_author.split()
        if len(tokens) > 1:
            # Check if the terminal word is an initial (e.g. "Smith J" or "Smith J.")
            if len(tokens[-1].rstrip('.')) <= 2 and tokens[-1].rstrip('.').isalpha():
                lastname = tokens[0]
            else:
                lastname = tokens[-1]
        else:
            lastname = tokens[0] if tokens else fallback

    # Safety fallback: clean any single hanging characters or initials
    lastname = re.sub(r'\s+[A-Za-z]\b.*$', '', lastname)
    lastname = lastname.strip().rstrip('.')

    if len(clean_authors) > 1:
        return f"{lastname} et al."
    return lastname


def resolve_duplicate_titles_and_registry(url_metadata_registry, ref_num_to_url):
    """
    Identifies duplicate titles within the registry, chooses the superior metadata
    profile (journal record vs fallback web-scrape), and consolidates document links.
    """
    title_to_urls = {}

    for url, meta in url_metadata_registry.items():
        norm_title = re.sub(r'[^a-z0-9]', '', meta['title'].lower().strip())
        if not norm_title:
            continue
        title_to_urls.setdefault(norm_title, []).append((url, meta))

    for norm_title, matches in title_to_urls.items():
        if len(matches) > 1:
            # Rank based on the presence of a journal name and clean author layouts
            sorted_matches = sorted(
                matches,
                key=lambda x: (1 if x[1].get('journal') else 0, len(x[1]['display'])),
                reverse=True
            )
            best_url, best_meta = sorted_matches[0]
            print(f"⚠️ Duplicate Title Detected: '{best_meta['title']}'")

            for duplicate_url, _ in sorted_matches[1:]:
                print(f"  🔗 Merging resource {duplicate_url} into verified master record {best_url}")
                # Remap the reference numbering assignments
                for ref_num, current_url in list(ref_num_to_url.items()):
                    if current_url == duplicate_url:
                        ref_num_to_url[ref_num] = best_url
                # Remove the duplicate metadata entry
                if duplicate_url in url_metadata_registry:
                    del url_metadata_registry[duplicate_url]

    return url_metadata_registry, ref_num_to_url


def fetch_doi_from_meta_tags(url):
    """
    Directly scraps target page headers to capture high-fidelity academic citation tags.
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            doi_match = re.search(r'<meta\s+name=["\']citation_doi["\']\s+content=["\']([^"\']+)["\']', res.text, re.IGNORECASE)
            if doi_match:
                return doi_match.group(1).strip()
    except Exception:
        pass
    return None


def is_academic_record(metadata, url):
    """
    Evaluates resolved metadata and URL to determine if the source
    qualifies as a legitimate scientific paper or academic registry entry.
    """
    authors, year, title, journal = metadata
    url_lower = url.lower()
    journal_lower = journal.lower()
    title_lower = title.lower()

    # 1. Hard Blacklist of Explicitly Non-Academic Domains & TLDs
    NON_ACADEMIC_DOMAINS = [
        'youtube.com', 'youtu.be', 'wikipedia.org', 'twitter.com', 'x.com',
        'github.com', 'medium.com', 'nytimes.com', 'bloomberg.com', 'forbes.com',
        'reddit.com', 'news', 'blog', 'vlog', 'amazon.com', 'scribbr.com'
    ]
    if any(domain in url_lower for domain in NON_ACADEMIC_DOMAINS):
        return False

    # 2. Catch Fallback Traces from Web Scrapers
    # If it has no true journal/platform and matched fallback signatures, drop it
    INVALID_JOURNALS = ['web resource', 'web', 'journal pdf', 'unknown']
    if journal_lower in INVALID_JOURNALS or not journal:
        # Check if a valid DOI or database ID was synthesized anyway
        has_doi = re.search(r'10\.\d{4,9}/', url) or 'arxiv' in url_lower or 'pubmed' in url_lower
        if not has_doi:
            return False

    # 3. Catch Anti-Bot/Page Error Artifacts
    ERROR_KEYWORDS = ['verifying your browser', '403 forbidden', 'not found', 'cloudflare', 'attention required']
    if any(err in title_lower for err in ERROR_KEYWORDS):
        return False

    # 4. Strict Structure Check: Papers must have a title and at least one author/org
    if not title or title.strip() == "Academic Reference":
        return False

    if not authors or authors == ["Unknown"]:
        return False

    return True


def filter_references_and_text(raw_text, url_list, citation_style="numbered"):
    """
    Filters out non-scientific URLs, updates the bibliography, and cleanses
    the corresponding in-text citations inside the manuscript text.

    Supported citation_style: 'numbered' (e.g., [1], [2]) or 'author-year' (e.g., (Smith, 2024))
    """
    valid_bibliography = []
    url_to_meta_map = {}

    # Track old indexing positions to assist with text re-indexing
    old_index_to_new_index = {}
    old_position = 1
    new_position = 1

    # Pass 1: Filter and Map Academic Integrity
    for url in url_list:
        meta = get_live_metadata(url)  # Calls your existing metadata function

        if is_academic_record(meta, url):
            valid_bibliography.append((url, meta))
            url_to_meta_map[url] = meta
            old_index_to_new_index[old_position] = new_position
            new_position += 1
        else:
            old_index_to_new_index[old_position] = None  # Flagged for deletion

        old_position += 1

    # Pass 2: Rewrite In-Text Citations
    clean_text = raw_text

    if citation_style == "numbered":
        # Match numbered markers like [1], [2], [1, 2, 3]
        def reindex_match(match):
            content = match.group(1)
            # Split out multi-citations like [1, 2]
            indices = [int(x.strip()) for x in content.split(',') if x.strip().isdigit()]
            new_indices = []

            for idx in indices:
                new_idx = old_index_to_new_index.get(idx)
                if new_idx is not None:
                    new_indices.append(str(new_idx))

            if new_indices:
                return f"[{', '.join(new_indices)}]"
            return ""  # Drops the citation marker entirely if it contained only non-scientific entries

        clean_text = re.sub(r'\[([\d\s,]+)\]', reindex_match, clean_text)
        # Clean up double spaces or trailing punctuation errors caused by dropped brackets
        clean_text = re.sub(r'\s+([.,;])', r'\1', clean_text)

    elif citation_style == "author-year":
        # Extract the metadata elements dropped during filtering
        dropped_items = [get_live_metadata(url) for url in url_list if not is_academic_record(get_live_metadata(url), url)]

        for item in dropped_items:
            authors, year, _, _ = item
            if authors and authors != ["Unknown"]:
                # Construct possible in-text variations: "Smith et al., 2024" or "Smith, 2024"
                lead_author = authors[0].split(',')[0].strip()
                patterns = [
                    rf'\({lead_author}\s+et\s+al\.,\s*{year}\)',
                    rf'\({lead_author},\s*{year}\)'
                ]
                for pattern in patterns:
                    clean_text = re.sub(pattern, '', clean_text, flags=re.IGNORECASE)

        # Polish dangling spacing or empty parenthesis artifacts
        clean_text = re.sub(r'\(\s*\)', '', clean_text)
        clean_text = re.sub(r'\s+([.,;])', r'\1', clean_text)

    return clean_text, valid_bibliography


def _parse_crossref_item(item):
    """
    Internal helper to uniformly parse a Crossref API item response payload
    into the standard tuple structure: (authors, year, title, journal).
    """
    title = "Academic Reference"
    if item.get('title'):
        title = item['title'][0] if isinstance(item['title'], list) and item['title'] else str(item['title'])

    journal = ""
    if item.get('container-title'):
        journal = item['container-title'][0] if isinstance(item['container-title'], list) and item['container-title'] else str(item['container-title'])
    elif item.get('institution'):
        journal = item['institution'][0].get('name', '') if isinstance(item['institution'], list) else item['institution'].get('name', '')
    if not journal:
        journal = "Journal Resource"

    authors = []
    if item.get('author'):
        for au in item['author']:
            family, given = au.get('family', ''), au.get('given', '')
            authors.append(f"{family}, {given}" if family and given else family)
    authors = [au.strip() for au in authors if au and au.strip()]
    if not authors:
        authors = ["Unknown"]

    year = "2026"
    for date_field in ['published-print', 'published-online', 'created', 'issued']:
        if item.get(date_field) and item[date_field].get('date-parts') and item[date_field]['date-parts'][0]:
            year = str(item[date_field]['date-parts'][0][0])
            break

    return authors, year, title, journal


def fetch_crossref_by_doi(doi):
    """
    Queries the Crossref API directly using a verified DOI string to
    retrieve high-fidelity academic journal metadata.
    """
    polite_headers = {
        'User-Agent': 'AcademicMetadataParser/2.0 (mailto:gurkpeter@yahoo.com; ResilientBatchScript)',
        'Accept': 'application/json'
    }
    try:
        clean_doi = doi.strip()
        clean_doi = re.sub(r'v\d+$', '', clean_doi, flags=re.IGNORECASE)
        api_url = f"https://api.crossref.org/works/{urllib.parse.quote(clean_doi, safe='/')}"
        req = urllib.request.Request(api_url, headers=polite_headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            item = json.loads(response.read().decode())['message']
            return _parse_crossref_item(item)
    except Exception:
        return None


def query_crossref_by_text(query):
    """
    Queries the Crossref API search endpoint with a raw string query fallback
    to find and return the single closest matching metadata record.
    """
    polite_headers = {
        'User-Agent': 'AcademicMetadataParser/2.0 (mailto:gurkpeter@yahoo.com; ResilientBatchScript)',
        'Accept': 'application/json'
    }
    try:
        api_url = f"https://api.crossref.org/works?query={urllib.parse.quote(query)}&rows=1"
        req = urllib.request.Request(api_url, headers=polite_headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            items = json.loads(response.read().decode())['message']['items']
            if items:
                return _parse_crossref_item(items[0])
    except Exception:
        return None


_LEADING_REF_NUM_RE = re.compile(r'^\s*[\[\(]?(\d{1,4})[\]\)\.\-:]\s+')


def _extract_leading_ref_number(text):
    """
    Extracts a genuine leading reference-list numeral from raw bibliography
    paragraph text (e.g. "7. Smith J..." / "[7] Smith J..." / "7) Smith J...").
    Only matches a numeral anchored at the very start of the paragraph and
    immediately followed by a delimiter + whitespace.

    This deliberately replaces the old `re.search(r'\b(\d+)\b', text)` fallback,
    which scanned the *entire* paragraph for any digit run and frequently
    grabbed an embedded publication year (or DOI fragment) instead of the true
    reference index -- causing silent ref_num_to_url collisions.
    """
    match = _LEADING_REF_NUM_RE.match(text)
    return match.group(1) if match else None


def register_reference(ref_num_to_url, used_ref_nums, candidate_ref_num, url, collision_log):
    """
    Safely inserts a (ref_num -> url) mapping, guaranteeing the key is unique.

    Previously, a bare `ref_num_to_url[ref_num] = url` meant that if two
    references ever resolved to the same key, the *first* reference's URL
    silently vanished from the pipeline with no warning. Here, a collision
    generates a synthetic suffixed key for the new entry instead, and logs it,
    so no reference is ever silently dropped.

    Returns the ref_num actually used as the key.
    """
    ref_num = candidate_ref_num
    if ref_num in used_ref_nums:
        original = ref_num
        suffix = 1
        while ref_num in used_ref_nums:
            suffix += 1
            ref_num = f"{original}_dup{suffix}"
        collision_log.append((original, ref_num, ref_num_to_url.get(original), url))
        print(f"⚠️  Reference numbering collision on marker [{original}]: an earlier reference "
              f"('{ref_num_to_url.get(original)}') already claimed this number. The new URL "
              f"('{url}') is preserved under internal key [{ref_num}] instead of silently "
              f"overwriting the earlier mapping -- it will still be resolved and included in the "
              f"RIS export, but will NOT auto-link to an in-text [n] marker. Check the source "
              f"document's numbering manually.")

    used_ref_nums.add(ref_num)
    ref_num_to_url[ref_num] = url
    return ref_num


def disambiguate_author_year_collisions(url_metadata_registry):
    """
    Detects distinct source URLs that would render identical {Display, Year}
    in-text citation markers (e.g. two unrelated 'Smith, 2024' papers, or two
    failed lookups that both collapsed to the same generic fallback such as
    'Unknown, 2026'). Adds a disambiguating a/b/c suffix to a *separate*
    'marker_year' field used only for the in-text citation text.

    The RIS record's real 'year' (Publication Year) field is left untouched,
    so the item's actual bibliographic date stays correct after Zotero import
    -- only the searchable marker text is disambiguated.
    """
    groups = {}
    for url, meta in url_metadata_registry.items():
        meta.setdefault('marker_year', meta['year'])
        key = (meta['display'], meta['year'])
        groups.setdefault(key, []).append(url)

    collisions_found = []
    suffixes = 'abcdefghijklmnopqrstuvwxyz'

    for (display, year), urls in groups.items():
        if len(urls) > 1:
            collisions_found.append((display, year, urls))
            for i, url in enumerate(urls):
                suffix = suffixes[i] if i < len(suffixes) else str(i)
                marker_year = f"{year}{suffix}"
                url_metadata_registry[url]['marker_year'] = marker_year
                print(f"⚠️  Ambiguous marker collision: '{{{display}, {year}}}' shared by "
                      f"{len(urls)} distinct source(s) -> in-text marker disambiguated to "
                      f"'{{{display}, {marker_year}}}' for {url} "
                      f"(RIS Publication Year field remains the true '{year}').")

    return url_metadata_registry, collisions_found


def print_collision_summary(ref_num_collisions, marker_collisions, url_metadata_registry):
    """
    Prints one consolidated end-of-run report surfacing every ambiguity the
    pipeline auto-corrected, so the user finds out proactively instead of
    only discovering it when Zotero's RTF Scan prompts mid-workflow.
    """
    print("\n📊 Collision Summary")
    if ref_num_collisions:
        print(f"⚠️  {len(ref_num_collisions)} in-text marker numbering collision(s) found in the source document (Step 1):")
        for original, dup_key, first_url, second_url in ref_num_collisions:
            print(f"   • marker [{original}] is claimed by two source references:")
            print(f"       1) {first_url}  (kept as [{original}])")
            print(f"       2) {second_url}  (preserved under internal key [{dup_key}] -- resolved into the RIS "
                  f"export, but NOT auto-linked to any [n] marker in the text; check the source numbering manually).")

    if marker_collisions:
        total_urls_affected = sum(len(urls) for _, _, urls in marker_collisions)
        print(f"⚠️  {len(marker_collisions)} distinct {{Author, Year}} collision group(s) auto-suffixed "
              f"({total_urls_affected} references affected) -- verify these in Zotero after import:")
        for display, year, urls in marker_collisions:
            print(f"   • {{{display}, {year}}} shared by {len(urls)} distinct sources:")
            for u in urls:
                print(f"       - {{{display}, {url_metadata_registry[u]['marker_year']}}}  ({u})")

    if not ref_num_collisions and not marker_collisions:
        print("✅ No ambiguous reference collisions detected -- every marker maps to exactly one source.")


def convert(input_docx, output_docx="marked_document.docx", output_ris="zotero_import.ris"):
    """
    Scans document references, normalizes academic metadata with full author profiles,
    prioritizes the latest bioRxiv preprints, eliminates duplicate titles, disambiguates
    author/year in-text marker collisions, and exports RIS files.
    """
    doc = Document(input_docx)
    ref_num_to_url = {}
    used_ref_nums = set()
    ref_num_collisions = []
    url_pattern = re.compile(r'https?://\S+')
    text_ref_pattern = re.compile(r'(\d+)\s*[\.\s\t)\]\-:]+\s*(https?://\S+)')
    native_list_counter = 1

    print("🔍 Step 1: Scanning document structure for references...")
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text: continue

        url_match = url_pattern.search(text)
        if not url_match: continue
        url = url_match.group(0).rstrip('.,] ) ')

        text_match = text_ref_pattern.search(text)
        if text_match:
            candidate_ref_num = text_match.group(1)
        elif bool(para._element.xpath('./w:pPr/w:numPr')) or para.style.name.startswith('List Number'):
            candidate_ref_num = str(native_list_counter)
            native_list_counter += 1
        else:
            # 🔴 FIX: only trust a genuine leading numeral marker; never scan the
            # whole paragraph for an arbitrary digit run (which often grabbed a
            # publication year instead of the true reference index).
            leading_num = _extract_leading_ref_number(text)
            if leading_num:
                candidate_ref_num = leading_num
            else:
                candidate_ref_num = str(native_list_counter)
                native_list_counter += 1

        # 🔴 FIX: never let a later reference silently clobber an earlier one
        # sharing the same key.
        register_reference(ref_num_to_url, used_ref_nums, candidate_ref_num, url, ref_num_collisions)

    if not ref_num_to_url:
        print("❌ Error: Could not extract references containing metadata targets.")
        return

    # 🔴 FILTER 1: Prioritize and remap bioRxiv version configurations
    ref_num_to_url = optimize_biorxiv_versions(ref_num_to_url)

    # 🔴 Use dict.fromkeys instead of set(...) to preserve first-seen order
    # deterministically. Disambiguation below assigns suffixes (a, b, c...)
    # based on encounter order, so this keeps results reproducible across runs
    # instead of depending on Python's randomized set/hash ordering.
    unique_urls = list(dict.fromkeys(ref_num_to_url.values()))

    print("\n🌐 Step 2: Fetching deep metadata and handling provider exceptions...")
    url_metadata_registry = {}

    for url in unique_urls:
        meta = None

        # High-fidelity resolution for Oxford University Press (OUP) URLs
        if 'academic.oup.com' in url.lower():
            oup_match = re.search(r'/article/.*?/(\d+)(?:\?|$)', url) or re.search(r'/article/(\d+)', url)
            if oup_match:
                article_id = oup_match.group(1)
                print(f"  🎯 Extracted OUP Article ID: {article_id}. Resolving target meta-tags...")

                # Use live DOM meta tag scraping to extract the explicit DOI securely
                scraped_doi = fetch_doi_from_meta_tags(url)
                if scraped_doi:
                    meta = fetch_crossref_by_doi(scraped_doi)  # Route via standard DOI function

                if not meta:
                    # Alternative text query if page scraping is blocked
                    meta = query_crossref_by_text(f"Oxford OUP {article_id}")

        # Fall back to default search routes if not handled by custom OUP code blocks
        if not meta:
            meta = get_live_metadata(url)

        if meta:
            authors, year, title, journal = meta
            # 🔴 FILTER 2: Enforce proper "Lastname et al." layouts without lingering middle initials
            display_name = get_display_author(authors)

            url_metadata_registry[url] = {
                'type': 'JOUR', 'authors': authors, 'display': display_name, 'year': year, 'title': title, 'journal': journal
            }
            print(f"  ✅ Asset Found: {display_name} ({year})")

    # 🔴 FILTER 3: Resolve duplicate titles and merge reference assignments
    url_metadata_registry, ref_num_to_url = resolve_duplicate_titles_and_registry(url_metadata_registry, ref_num_to_url)

    # 🔴 FILTER 4: Detect and disambiguate {Display, Year} in-text marker
    # collisions so Zotero's RTF Scan never encounters two distinct sources
    # rendered as the exact same citation text.
    url_metadata_registry, marker_collisions = disambiguate_author_year_collisions(url_metadata_registry)

    print("\n📝 Step 3: Upgrading document in-text citation markers...")
    inline_pattern = re.compile(r'\[(\d+)\]')

    for para in doc.paragraphs:
        matches = inline_pattern.findall(para.text)
        if matches:
            new_text = para.text
            for ref_num in matches:
                if ref_num in ref_num_to_url:
                    url = ref_num_to_url[ref_num]
                    if url in url_metadata_registry:
                        meta = url_metadata_registry[url]
                        marker_year = meta.get('marker_year', meta['year'])
                        new_text = new_text.replace(f"[{ref_num}]", f"{{{meta['display']}, {marker_year}}}")
            para.text = new_text

    doc.save(output_docx)
    print(f"💾 File updates successfully written to: {output_docx}")

    print("\n📁 Step 4: Formatting and outputting Zotero RIS database...")
    with open(output_ris, 'w', encoding='utf-8') as ris_file:
        for url, data in url_metadata_registry.items():
            ris_file.write(f"TY  - {data['type']}\n")
            for author in data['authors']:
                ris_file.write(f"AU  - {author}\n")
            ris_file.write(f"PY  - {data['year']}\n")  # true year -- unaffected by marker disambiguation
            ris_file.write(f"TI  - {data['title']}\n")
            if data['journal']: ris_file.write(f"JO  - {data['journal']}\n")
            ris_file.write(f"UR  - {url}\n")
            ris_file.write("ER  - \n\n")

    # 🔴 Priority 3: Proactively surface ambiguity instead of letting the user
    # discover it only when Zotero's RTF Scan prompts mid-workflow.
    print_collision_summary(ref_num_collisions, marker_collisions, url_metadata_registry)

    print(f"✅ Success!")


if __name__ == '__main__':
    fire.Fire(convert)