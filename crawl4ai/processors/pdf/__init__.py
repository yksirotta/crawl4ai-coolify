from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import asdict

from crawl4ai.async_logger import AsyncLogger
from crawl4ai.async_crawler_strategy import AsyncCrawlerStrategy
from crawl4ai.models import AsyncCrawlResponse, ScrapingResult 
from crawl4ai.content_scraping_strategy import ContentScrapingStrategy
from .processor import NaivePDFProcessorStrategy  # Assuming your current PDF code is in pdf_processor.py

class PDFCrawlerStrategy(AsyncCrawlerStrategy):
    def __init__(self, logger: AsyncLogger = None):
        self.logger = logger
        
    async def crawl(self, url: str, **kwargs) -> AsyncCrawlResponse:
        # Just pass through with empty HTML - scraper will handle actual processing
        return AsyncCrawlResponse(
            html="",  # Scraper will handle the real work
            response_headers={"Content-Type": "application/pdf"},
            status_code=200
        )
    
    async def close(self):
        pass        
        
    async def __aenter__(self):        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

class PDFContentScrapingStrategy(ContentScrapingStrategy):
    """
    A content scraping strategy for PDF files.
    
    Attributes:
        save_images_locally (bool): Whether to save images locally.
        extract_images (bool): Whether to extract images from PDF.
        image_save_dir (str): Directory to save extracted images.
        logger (AsyncLogger): Logger instance for recording events and errors.
        
    Methods:
        scrap(url: str, html: str, **params) -> ScrapingResult:
            Scrap content from a PDF file.
        ascrap(url: str, html: str, **kwargs) -> ScrapingResult:
            Asynchronous version of scrap.
            
    Usage:
        strategy = PDFContentScrapingStrategy(
            save_images_locally=False,
            extract_images=False,
            image_save_dir=None,
            logger=logger
        )
        
    """
    def __init__(self, 
                 save_images_locally=False,
                 extract_images=False,
                 image_save_dir=None,
                 logger: AsyncLogger = None):
        self.logger = logger
        self.pdf_processor = NaivePDFProcessorStrategy(
            save_images_locally=False,
            extract_images=False,
            image_save_dir=None
        )

    def scrap(self, url: str, html: str, **params) -> ScrapingResult:
        """
        Scrap content from a PDF file.
        
        Args:
            url (str): The URL of the PDF file.
            html (str): The HTML content of the page.
            **params: Additional parameters.
        
        Returns:
            ScrapingResult: The scraped content.
        """
        # Download if URL or use local path
        pdf_path = self._get_pdf_path(url)
        try:
            # Process PDF
            result = self.pdf_processor.process(Path(pdf_path))
            
            # Combine page HTML
            cleaned_html = f"""
        <html>
            <head><meta name="pdf-pages" content="{len(result.pages)}"></head>
            <body>
                {''.join(f'<div class="pdf-page" data-page="{i+1}">{page.html}</div>'
                         for i, page in enumerate(result.pages))}
            </body>
        </html>
        """
            
            # Accumulate media and links with page numbers
            media = {"images": []}
            links = {"urls": []}
            
            for page in result.pages:
                # Add page number to each image
                for img in page.images:
                    img["page"] = page.page_number
                    media["images"].append(img)
                
                # Add page number to each link
                for link in page.links:
                    links["urls"].append({
                        "url": link,
                        "page": page.page_number
                    })

            return ScrapingResult(
                cleaned_html=cleaned_html,
                success=True,
                media=media,
                links=links,
                metadata=asdict(result.metadata)
            )
        finally:
            # Cleanup temp file if downloaded
            if url.startswith(("http://", "https://")):
                Path(pdf_path).unlink(missing_ok=True)

    async def ascrap(self, url: str, html: str, **kwargs) -> ScrapingResult:
        # For simple cases, you can use the sync version
        return await asyncio.to_thread(self.scrap, url, html, **kwargs)
        

    def _get_pdf_path(self, url: str) -> str:
        if url.startswith(("http://", "https://")):
            import tempfile
            import requests
            
            # Create temp file with .pdf extension
            temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
            
            try:
                # Download PDF with streaming
                response = requests.get(url, stream=True)
                response.raise_for_status()
                
                # Write to temp file
                with open(temp_file.name, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        
                return temp_file.name
                
            except Exception as e:
                # Clean up temp file if download fails
                Path(temp_file.name).unlink(missing_ok=True)
                raise RuntimeError(f"Failed to download PDF from {url}: {str(e)}")
                
        elif url.startswith("file://"):
            return url[7:]  # Strip file:// prefix
            
        return url  # Assume local path
    

__all__ = ["PDFCrawlerStrategy", "PDFContentScrapingStrategy"]