"""Isolated local text extraction: no network, macros, or source-file writes."""
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

MAX_BYTES = 50 * 1024 * 1024
MAX_CHARS = 200_000
MAX_PAGES = 100

def redact(text):
    patterns = [r'\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{16,}',
                r'\bgh[pousr]_[A-Za-z0-9]{20,}', r'\bgithub_pat_[A-Za-z0-9_]{20,}',
                r'\bAKIA[A-Z0-9]{16}\b',
                r'(?im)^.*(?:api[_ -]?key|access[_ -]?token|secret[_ -]?key|authorization\s*[:=]|password\s*[:=]|密码\s*[:：=]).*$']
    count = 0
    for pat in patterns:
        text, n = re.subn(pat, '[疑似凭据已隐藏]', text)
        count += n
    return text, count

def extract(path):
    p = Path(path)
    st = p.stat()
    result = {"status":"unread", "source_size":st.st_size, "source_mtime_ns":st.st_mtime_ns}
    if st.st_size > MAX_BYTES:
        return {**result, "status":"oversize", "text":""}
    raw = p.read_bytes()
    result['sha256'] = hashlib.sha256(raw).hexdigest()
    ext = p.suffix.lower()
    truncated = False
    if ext == '.pdf':
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument(str(p))
        try:
            result['total_pages'] = len(doc)
            chunks, chars, read = [], 0, 0
            for i in range(min(len(doc), MAX_PAGES)):
                page = doc[i]
                text_page = page.get_textpage()
                try:
                    s = text_page.get_text_range()
                finally:
                    text_page.close()
                    page.close()
                chunks.append(f'\n\n### 原文第 {i+1} 页\n\n{s}')
                chars += len(s)
                read += 1
                if chars > MAX_CHARS:
                    break
            result['pages_read'] = read
            truncated = read < len(doc) or chars > MAX_CHARS
            text = ''.join(chunks)
            if chars < 30:
                return {**result, "status":"no_extractable_text", "text":"", "pages_read":read}
        finally:
            doc.close()
    elif ext in {'.docx', '.pptx'}:
        with zipfile.ZipFile(p) as archive:
            if ext == '.docx':
                names = [n for n in archive.namelist() if n == 'word/document.xml']
                ns = {'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                texts = []
                for n in names:
                    info = archive.getinfo(n)
                    if info.file_size > 40 * 1024 * 1024:
                        return {**result, "status":"oversize_xml", "text":""}
                    root = ET.fromstring(archive.read(n))
                    texts.extend(''.join(el.itertext()) for el in root.findall('.//w:p/w:r/w:t', ns))
                # Preserve paragraph order including table-cell paragraphs.
                texts = [''.join(t.text or '' for t in para.findall('.//w:t', ns))
                         for para in root.findall('.//w:p', ns)] if names else []
            else:
                names = sorted([n for n in archive.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml', n)],
                               key=lambda n:int(re.search(r'slide(\d+)', n).group(1)))
                ns = {'a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
                texts=[]
                for i,n in enumerate(names):
                    if archive.getinfo(n).file_size > 40 * 1024 * 1024:
                        return {**result, 'status':'oversize_xml', 'text':''}
                    root=ET.fromstring(archive.read(n))
                    texts.append(f'\n### 原文第 {i+1} 张幻灯片\n')
                    texts.extend(''.join(t.text or '' for t in para.findall('.//a:t', ns))
                                 for para in root.findall('.//a:p', ns))
            text = '\n'.join(texts)
    else:
        encoding = None
        for enc in ('utf-8-sig','utf-16','gb18030'):
            try:
                text=raw.decode(enc)
                encoding=enc
                break
            except UnicodeError:
                pass
        if encoding is None:
            return {**result, "status":"unsupported_encoding", "text":""}
        result['encoding']=encoding
        if '\x00' in text:
            return {**result, "status":"binary_text_file", "text":""}
    text = text.replace('\r\n','\n').replace('\x00','')
    if len(text)>MAX_CHARS:
        truncated=True
        text=text[:MAX_CHARS]
    text, redactions = redact(text)
    after=p.stat()
    if after.st_size != st.st_size or after.st_mtime_ns != st.st_mtime_ns:
        return {**result, "status":"source_changed_during_read", "text":""}
    return {**result, "status":"partial" if truncated else ("extracted" if text.strip() else "empty"),
            "redactions":redactions, "characters":len(text), "text":text}

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        result=extract(sys.argv[1])
    except Exception as exc:
        result={"status":"extraction_error", "error":type(exc).__name__, "text":""}
    print(json.dumps(result, ensure_ascii=False))
