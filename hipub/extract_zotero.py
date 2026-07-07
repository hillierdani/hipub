import io
import re
import json
import urllib.request
import urllib.parse
import datetime
import html as html_lib
import requests
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

    # 🔴 NCBI API Key Configuration
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
                        re.search(r'[\/_]pmc(\d{5,8})', url, re.IGNORECASE)
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
                api_url = f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='/')}"
                req = urllib.request.Request(api_url, headers=polite_headers)
                with urllib.request.urlopen(req, timeout=5) as response:
                    item = json.loads(response.read().decode())['message']
            except Exception:
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
        parsed_url = urllib.parse.urlparse(url)
        domain = parsed_url.netloc.replace('www.', '')
        domain_name = domain.split('.')[0].capitalize()
    except Exception:
        domain_name = "Weblink"

    author = f"{domain_name}_{ref_num}"
    year_match = re.search(r'\b(19[5-9]\d|20[0-2]\d)\b', url)
    year = year_match.group(0) if year_match else "2026"
    return [author], year, url


def optimize_biorxiv_versions(ref_num_to_url):
    """Scans reference mapping for bioRxiv URLs and updates older variants to latest version."""
    base_to_max_ver = {}

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
    """Extracts the clean primary surname and appends 'et al.' if multiple authors exist."""
    if not authors or not isinstance(authors, list):
        return fallback
    clean_authors = [a.strip() for a in authors if a and a.strip()]
    if not clean_authors:
        return fallback

    first_author = clean_authors[0]

    if ',' in first_author:
        lastname = first_author.split(',')[0].strip()
    else:
        tokens = first_author.split()
        if len(tokens) > 1:
            if len(tokens[-1].rstrip('.')) <= 2 and tokens[-1].rstrip('.').isalpha():
                lastname = tokens[0]
            else:
                lastname = tokens[-1]
        else:
            lastname = tokens[0] if tokens else fallback

    lastname = re.sub(r'\s+[A-Za-z]\b.*$', '', lastname)
    lastname = lastname.strip().rstrip('.')

    if len(clean_authors) > 1:
        return f"{lastname} et al."
    return lastname


def resolve_duplicate_titles_and_registry(url_metadata_registry, ref_num_to_url):
    url_remap = {}
    groups = {}
    for url, meta in url_metadata_registry.items():
        base_author = re.sub(r'_\d+$', '', meta['display'].lower().strip())
        year = meta['year']
        groups.setdefault((base_author, year), []).append((url, meta))

    def get_significant_words(title_str):
        return set(re.findall(r'\b[a-z]{3,}\b', title_str.lower()))

    for (author, year), items in groups.items():
        if len(items) < 2:
            continue

        merged_urls = set()
        for i in range(len(items)):
            url_i, meta_i = items[i]
            if url_i in merged_urls:
                continue

            words_i = get_significant_words(meta_i['title'])
            if not words_i:
                continue

            for j in range(i + 1, len(items)):
                url_j, meta_j = items[j]
                if url_j in merged_urls:
                    continue

                words_j = get_significant_words(meta_j['title'])
                if not words_j:
                    continue

                intersection = words_i.intersection(words_j)
                smaller_size = min(len(words_i), len(words_j))
                overlap_ratio = len(intersection) / smaller_size if smaller_size > 0 else 0

                if overlap_ratio >= 0.70:
                    is_i_preprint = 'biorxiv.org' in url_i.lower() or 'medrxiv.org' in url_i.lower()
                    is_j_preprint = 'biorxiv.org' in url_j.lower() or 'medrxiv.org' in url_j.lower()

                    if is_i_preprint and not is_j_preprint:
                        master_url, master_meta = url_j, meta_j
                        dup_url, dup_meta = url_i, meta_i
                    elif not is_i_preprint and is_j_preprint:
                        master_url, master_meta = url_i, meta_i
                        dup_url, dup_meta = url_j, meta_j
                    else:
                        if not meta_i.get('journal') or meta_i['journal'].lower() in ['web resource', 'web', 'journal pdf', 'unknown']:
                            master_url, master_meta = url_j, meta_j
                            dup_url, dup_meta = url_i, meta_i
                        else:
                            master_url, master_meta = url_i, meta_i
                            dup_url, dup_meta = url_j, meta_j

                    print(f"⚠️ Duplicate Paper Detected via Fuzzy Title Match: '{master_meta['title']}'")
                    print(f"   🔗 Merging preprint record {dup_url} -> peer-reviewed master {master_url}")

                    url_remap[dup_url] = master_url
                    merged_urls.add(dup_url)

                    for ref_num, current_url in list(ref_num_to_url.items()):
                        if current_url == dup_url:
                            ref_num_to_url[ref_num] = master_url

                    if dup_url in url_metadata_registry:
                        del url_metadata_registry[dup_url]

    return url_metadata_registry, ref_num_to_url, url_remap


def fetch_doi_from_meta_tags(url):
    """Directly scrapes target page headers to capture academic citation tags."""
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
    """Evaluates resolved metadata to ensure it fits valid academic standards."""
    authors, year, title, journal = metadata
    url_lower = url.lower()
    journal_lower = journal.lower()
    title_lower = title.lower()

    NON_ACADEMIC_DOMAINS = [
        'youtube.com', 'youtu.be', 'wikipedia.org', 'twitter.com', 'x.com',
        'github.com', 'medium.com', 'nytimes.com', 'bloomberg.com', 'forbes.com',
        'reddit.com', 'news', 'blog', 'vlog', 'amazon.com', 'scribbr.com'
    ]
    if any(domain in url_lower for domain in NON_ACADEMIC_DOMAINS):
        return False

    INVALID_JOURNALS = ['web resource', 'web', 'journal pdf', 'unknown']
    if journal_lower in INVALID_JOURNALS or not journal:
        has_doi = re.search(r'10\.\d{4,9}/', url) or 'arxiv' in url_lower or 'pubmed' in url_lower
        if not has_doi:
            return False

    ERROR_KEYWORDS = ['verifying your browser', '403 forbidden', 'not found', 'cloudflare', 'attention required']
    if any(err in title_lower for err in ERROR_KEYWORDS):
        return False

    if not title or title.strip() == "Academic Reference":
        return False

    if not authors or authors == ["Unknown"]:
        return False

    return True


def _parse_crossref_item(item):
    """Uniformly parses a Crossref API item response payload."""
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
    match = _LEADING_REF_NUM_RE.match(text)
    return match.group(1) if match else None


def register_reference(ref_num_to_url, used_ref_nums, candidate_ref_num, url, collision_log):
    ref_num = candidate_ref_num
    if ref_num in used_ref_nums:
        original = ref_num
        suffix = 1
        while ref_num in used_ref_nums:
            suffix += 1
            ref_num = f"{original}_dup{suffix}"
        collision_log.append((original, ref_num, ref_num_to_url.get(original), url))
        print(f"⚠️  Reference numbering collision on marker [{original}] detected.")

    used_ref_nums.add(ref_num)
    ref_num_to_url[ref_num] = url
    return ref_num


def print_collision_summary(ref_num_collisions):
    """Surfaces document text index irregularities proactively."""
    print("\n📊 Collision Summary")
    if ref_num_collisions:
        print(f"⚠️  {len(ref_num_collisions)} in-text marker numbering collision(s) found in the source document:")
        for original, dup_key, first_url, second_url in ref_num_collisions:
            print(f"   • marker [{original}] is claimed by two source references:")
            print(f"       1) {first_url}  (kept as [{original}])")
            print(f"       2) {second_url}  (preserved under internal key [{dup_key}])")
    else:
        print("Hexadecimal alignment confirmed: No collision parsing defects discovered.")


def convert(input_docx, output_docx="marked_document.docx", output_ris="zotero_import.ris"):
    """
    Scans document references, normalizes academic metadata, isolates bioRxiv updates,
    embeds unique native triple strings into Word paragraphs, and exports pure RIS records.
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
            leading_num = _extract_leading_ref_number(text)
            if leading_num:
                candidate_ref_num = leading_num
            else:
                candidate_ref_num = str(native_list_counter)
                native_list_counter += 1

        register_reference(ref_num_to_url, used_ref_nums, candidate_ref_num, url, ref_num_collisions)

    if not ref_num_to_url:
        print("❌ Error: Could not extract references containing metadata targets.")
        return

    # 🔴 FILTER 1: Prioritize and remap bioRxiv version configurations
    ref_num_to_url = optimize_biorxiv_versions(ref_num_to_url)

    # Preserve extraction order deterministically
    unique_urls = list(dict.fromkeys(ref_num_to_url.values()))

    # 🔴 FIX INTEGRATION: Fetch deep metadata without name-mangling suffixes
    print("\n🌐 Step 2: Fetching deep metadata and handling provider exceptions...")
    url_metadata_registry = {}

    for url in unique_urls:
        meta = None

        if 'academic.oup.com' in url.lower():
            oup_match = re.search(r'/article/.*?/(\d+)(?:\?|$)', url) or re.search(r'/article/(\d+)', url)
            if oup_match:
                article_id = oup_match.group(1)
                print(f"  🎯 Extracted OUP Article ID: {article_id}. Resolving target meta-tags...")

                scraped_doi = fetch_doi_from_meta_tags(url)
                if scraped_doi:
                    meta = fetch_crossref_by_doi(scraped_doi)

                if not meta:
                    meta = query_crossref_by_text(f"Oxford OUP {article_id}")

        if not meta:
            meta = get_live_metadata(url)

        if meta:
            authors, year, title, journal = meta
            display_name = get_display_author(authors)
            title = re.sub(r'\s+', ' ', title).strip()

            # Generate unique citekey for Pandoc mapping
            author_clean = re.sub(r'[^a-zA-Z]', '', display_name.split()[0])
            citekey = f"{author_clean}{year}"
            while any(d.get('citekey') == citekey for d in url_metadata_registry.values()):
                citekey += "a"

            url_metadata_registry[url] = {
                'type': 'JOUR', 'authors': authors, 'display': display_name, 'year': year, 'title': title, 'journal': journal, 'citekey': citekey
            }
            print(f"  ✅ Asset Found: {display_name} ({year})")

    # 🔴 FILTER 3: Resolve duplicate titles and merge reference assignments
    url_metadata_registry, ref_num_to_url, url_remap = resolve_duplicate_titles_and_registry(url_metadata_registry, ref_num_to_url)

    # 🔴 FIX INTEGRATION: Disambiguate collisions and convert to Pandoc format
    print("\n📝 Step 3: Upgrading document in-text citation markers to Pandoc format...")

    # 1. Detect Author-Year collisions
    author_year_groups = {}
    for url, meta in url_metadata_registry.items():
        display = meta['display']
        base_author = display.replace(' et al.', '').strip() if ' et al.' in display else display.strip()
        year = meta['year']
        group_key = f"{base_author.lower()}|{year}"

        if group_key not in author_year_groups:
            author_year_groups[group_key] = []
        author_year_groups[group_key].append(url)

    # Assign disambiguation suffixes (a, b, c...) only to colliding groups
    for group_key, urls in author_year_groups.items():
        if len(urls) > 1:
            urls_sorted = sorted(urls, key=lambda u: url_metadata_registry[u]['title'])
            for idx, url in enumerate(urls_sorted):
                suffix = chr(ord('a') + idx)
                url_metadata_registry[url]['disambiguation_suffix'] = suffix
        else:
            url_metadata_registry[urls[0]]['disambiguation_suffix'] = ""

    inline_num_pattern = re.compile(r'\[(\d+)\]')

    for para in doc.paragraphs:
        text = para.text
        if not text:
            continue

        # Convert numeric markers [1] to Pandoc format [@citekey]
        matches = inline_num_pattern.findall(text)
        if matches:
            for ref_num in matches:
                if ref_num in ref_num_to_url:
                    url = ref_num_to_url[ref_num]
                    if url in url_metadata_registry:
                        meta = url_metadata_registry[url]
                        suffix = meta.get('disambiguation_suffix', '')
                        # Pandoc marker syntax: [@citekey]
                        pandoc_marker = f"[@{meta['citekey']}{suffix}]"
                        text = text.replace(f"[{ref_num}]", pandoc_marker)

            # Merge adjacent Pandoc markers: [@A][@B] -> [@A; @B]
            text = re.sub(r'\]\s*\[@', '; @', text)

        para.text = text

    doc.save(output_docx)
    print(f"💾 File updates successfully written to: {output_docx}")

    # 🔴 FIX INTEGRATION: Output Zotero RIS database with M2 tag for guaranteed Citation Key mapping
    output_ris_file = output_ris if output_ris.endswith('.ris') else output_ris.replace('.bib', '.ris')
    print(f"\n📁 Step 4: Formatting and outputting Zotero RIS database to {output_ris_file}...")

    with open(output_ris_file, 'w', encoding='utf-8') as ris_file:
        for url, data in url_metadata_registry.items():
            suffix = data.get('disambiguation_suffix', '')
            unique_citekey = f"{data['citekey']}{suffix}"
            disambiguated_year = f"{data['year']}{suffix}"

            ris_file.write("TY  - JOUR\n")
            ris_file.write(f"ID  - {unique_citekey}\n")
            ris_file.write(f"TI  - {data['title']}\n")

            for author in data['authors']:
                # RIS requires "Last, First" or "Last, First Init" format
                ris_file.write(f"AU  - {author}\n")

            ris_file.write(f"PY  - {disambiguated_year}\n")

            if data['journal']:
                ris_file.write(f"JO  - {data['journal']}\n")

            ris_file.write(f"UR  - {url}\n")

            # CRITICAL FIX: The M2 tag maps natively to Zotero's "Extra" field.
            # Zotero natively parses "Citation Key: " from the Extra field and locks it into the metadata pane.
            ris_file.write(f"M2  - Citation Key: {unique_citekey}\n")

            ris_file.write("ER  - \n\n")

    print(f"💾 RIS file successfully written. Import this .ris file into Zotero.")

    print_collision_summary(ref_num_collisions)
    print(f"✅ Success!")


if __name__ == '__main__':
    fire.Fire(convert)