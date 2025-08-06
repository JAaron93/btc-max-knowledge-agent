import json
import os
import time
from typing import Any, Dict, List, Tuple

import feedparser
import requests
from newspaper import Article

from btc_max_knowledge_agent.monitoring.url_metadata_monitor import URLMetadataMonitor
from utils.url_error_handler import (
    FallbackURLStrategy,
    GracefulDegradation,
    URLValidationError,
    exponential_backoff_retry,
)
from utils.url_metadata_logger import URLMetadataLogger, correlation_context

# Import enhanced URL utilities and error handling
from utils.url_utils import extract_domain, sanitize_url_for_storage, validate_url_batch

# Add src to path to ensure imports work


class BitcoinDataCollector:
    def __init__(self, check_url_accessibility: bool = False):
        self.session = requests.Session()
        # Rotate through a small pool of modern User-Agents to reduce 4xx and fingerprinting
        user_agents = [
            # Recent stable Chrome-like UA
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            # Recent stable Firefox-like UA
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 13.3; rv:124.0) Gecko/20100101 Firefox/124.0",
            # Recent stable Edge-like UA
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
        ]
        # Simple rotation using time-based index to avoid static UA without additional deps
        ua = user_agents[int(time.time()) % len(user_agents)]
        self.session.headers.update({"User-Agent": ua})

        # Configuration for URL validation behavior
        self.check_url_accessibility = check_url_accessibility

        # Initialize logging
        self.validation_logger = URLMetadataLogger.get_logger("validation")
        self.metrics_logger = URLMetadataLogger.get_logger("metrics")
        self.monitor = URLMetadataMonitor()

        # Bitcoin and blockchain sources
        self.sources = {
            "bitcoin_org": "https://bitcoin.org/en/",
            "lightning_network": "https://lightning.network/",
            "bitcoin_wiki": "https://en.bitcoin.it/wiki/Main_Page",
            "coindesk_bitcoin": "https://www.coindesk.com/tag/bitcoin/",
            "cointelegraph_bitcoin": "https://cointelegraph.com/tags/bitcoin",
            "bitcoin_magazine": "https://bitcoinmagazine.com/",
        }

        # RSS feeds for news
        self.rss_feeds = [
            "https://bitcoinmagazine.com/feed",
            "https://www.coindesk.com/arc/outboundfeeds/rss/",
            "https://cointelegraph.com/rss",
        ]

    def set_url_accessibility_check(self, enabled: bool) -> None:
        """
        Set whether URL accessibility checking should be performed during batch validation.

        Args:
            enabled: True to enable accessibility checks, False to disable
        """
        self.check_url_accessibility = enabled
        self.validation_logger.info(
            f"URL accessibility checking {'enabled' if enabled else 'disabled'}"
        )

    def get_url_accessibility_check(self) -> bool:
        """
        Get the current URL accessibility checking setting.

        Returns:
            bool: True if accessibility checks are enabled, False otherwise
        """
        return self.check_url_accessibility

    @exponential_backoff_retry(
        max_retries=3,
        exceptions=(requests.RequestException, Exception),
        raise_on_exhaust=False,
        fallback_result=[],
    )
    def collect_from_rss(self, max_articles: int = 20) -> List[Dict[str, Any]]:
        """Collect articles from RSS feeds with retry logic"""
        articles: List[Dict[str, Any]] = []

        with correlation_context() as correlation_id:
            self.validation_logger.info(
                "Starting RSS collection",
                extra={
                    "correlation_id": correlation_id,
                    "max_articles": max_articles,
                    "feed_count": len(self.rss_feeds),
                },
            )

        for feed_url in self.rss_feeds:
            with correlation_context() as feed_correlation_id:
                try:
                    print(f"Fetching RSS feed: {feed_url}")
                    self.validation_logger.info(
                        "Fetching RSS feed",
                        extra={
                            "correlation_id": feed_correlation_id,
                            "feed_url": feed_url,
                        },
                    )

                    start_time = time.time()
                    # Fetch RSS feed with timeout using requests session
                    response = self.session.get(feed_url, timeout=10)
                    response.raise_for_status()
                    # Parse the RSS content with feedparser
                    feed = feedparser.parse(response.content)
                    feed_fetch_duration = (time.time() - start_time) * 1000

                    self.metrics_logger.info(
                        "RSS feed fetched",
                        extra={
                            "correlation_id": feed_correlation_id,
                            "feed_url": feed_url,
                            "duration_ms": feed_fetch_duration,
                            "entry_count": len(feed.entries),
                        },
                    )

                    for entry in feed.entries[:max_articles]:
                        try:
                            article_start = time.time()
                            self.validation_logger.info(
                                "Processing article",
                                extra={
                                    "correlation_id": feed_correlation_id,
                                    "article_url": entry.link,
                                    "feed_url": feed_url,
                                },
                            )

                            article = Article(entry.link)
                            article.download()
                            article.parse()

                            article_duration = (time.time() - article_start) * 1000

                            if (
                                len(article.text) > 500
                            ):  # Only include substantial articles
                                # Sanitize URL before adding
                                sanitized_url = sanitize_url_for_storage(entry.link)
                                if not sanitized_url:
                                    sanitized_url = FallbackURLStrategy.domain_only_url(
                                        entry.link
                                    )

                                article_data = {
                                    "id": f"rss_{len(articles)}",
                                    "title": entry.title,
                                    "content": article.text,
                                    "source": feed_url,
                                    "category": "news",
                                    "url": sanitized_url or entry.link,
                                    "published": entry.get("published", ""),
                                }
                                articles.append(article_data)

                                self.validation_logger.info(
                                    "Article extracted successfully",
                                    extra={
                                        "correlation_id": feed_correlation_id,
                                        "article_url": entry.link,
                                        "article_title": entry.title,
                                        "content_length": len(article.text),
                                        "duration_ms": article_duration,
                                    },
                                )

                                # Record URL extraction metric
                                self.monitor.record_validation(
                                    url=entry.link,
                                    valid=True,
                                    duration_ms=article_duration,
                                    correlation_id=feed_correlation_id,
                                )
                            else:
                                self.validation_logger.warning(
                                    "Article too short",
                                    extra={
                                        "correlation_id": feed_correlation_id,
                                        "article_url": entry.link,
                                        "content_length": len(article.text),
                                    },
                                )

                            time.sleep(1)  # Be respectful

                        except Exception as e:
                            print(f"Error processing article {entry.link}: {e}")
                            self.validation_logger.error(
                                "Failed to process article",
                                extra={
                                    "correlation_id": feed_correlation_id,
                                    "article_url": entry.link,
                                    "error": str(e),
                                },
                            )

                            # Record failure metric
                            self.monitor.record_validation(
                                url=entry.link,
                                valid=False,
                                duration_ms=(time.time() - article_start) * 1000,
                                error=str(e),
                                correlation_id=feed_correlation_id,
                            )
                            continue

                except Exception as e:
                    print(f"Error fetching RSS feed {feed_url}: {e}")
                    self.validation_logger.error(
                        "Failed to fetch RSS feed",
                        extra={
                            "correlation_id": feed_correlation_id,
                            "feed_url": feed_url,
                            "error": str(e),
                        },
                    )
                    continue

        self.metrics_logger.info(
            "RSS collection completed",
            extra={
                "total_articles": len(articles),
                "feeds_processed": len(self.rss_feeds),
            },
        )

        return articles

    @exponential_backoff_retry(
        max_retries=3,
        exceptions=(URLValidationError, Exception),
        raise_on_exhaust=False,
    )
    def collect_bitcoin_basics(self) -> List[Dict[str, Any]]:
        """Collect basic Bitcoin information with enhanced URL validation"""
        documents = []

        with correlation_context() as correlation_id:
            self.validation_logger.info(
                "Collecting Bitcoin basics", extra={"correlation_id": correlation_id}
            )

            # Define educational resources with comprehensive URLs
            resources = [
                {
                    "id": "bitcoin_whitepaper",
                    "title": "Bitcoin: A Peer-to-Peer Electronic Cash System",
                    "content": (
                        """Bitcoin is a peer-to-peer electronic cash system that allows online payments to be sent directly from one party to another without going through a financial institution. Digital signatures provide part of the solution, but the main benefits are lost if a trusted third party is still required to prevent double-spending. We propose a solution to the double-spending problem using a peer-to-peer network. The network timestamps transactions by hashing them into an ongoing chain of hash-based proof-of-work, forming a record that cannot be changed without redoing the proof-of-work. The longest chain not only serves as proof of the sequence of events witnessed, but proof that it came from the largest pool of CPU power."""
                    ),
                    "source": "bitcoin.org",
                    "category": "fundamentals",
                    "url": "https://bitcoin.org/bitcoin.pdf",
                    "canonical_urls": [
                        "https://bitcoin.org/bitcoin.pdf",
                        "https://bitcoin.org/en/bitcoin-paper",
                    ],
                },
                {
                    "id": "lightning_network_basics",
                    "title": "Lightning Network Overview",
                    "content": (
                        """The Lightning Network is a "Layer 2" payment protocol layered on top of Bitcoin. It enables fast transactions between participating nodes and has been proposed as a solution to the bitcoin scalability problem. It features a peer-to-peer system for making micropayments of cryptocurrency through a network of bidirectional payment channels without delegating custody of funds. Normal use of the Lightning Network consists of opening a payment channel by committing a funding transaction to the relevant base blockchain, followed by making any number of Lightning Network transactions that update the tentative distribution of the channel's funds without broadcasting those to the blockchain, optionally followed by closing the payment channel by broadcasting the final version of the settlement transaction to distribute the channel's funds."""
                    ),
                    "source": "lightning.network",
                    "category": "layer2",
                    "url": "https://lightning.network/lightning-network-paper.pdf",
                    "canonical_urls": [
                        "https://lightning.network/lightning-network-paper.pdf",
                        "https://lightning.network/",
                        "https://github.com/lightning/bolts",
                    ],
                },
                {
                    "id": "blockchain_basics",
                    "title": "Understanding Blockchain Technology",
                    "content": (
                        """A blockchain is a distributed ledger with growing lists of records, called blocks, that are linked and secured using cryptography. Each block contains a cryptographic hash of the previous block, a timestamp, and transaction data. By design, a blockchain is resistant to modification of its data. This is because once recorded, the data in any given block cannot be altered retroactively without altering all subsequent blocks. For use as a distributed ledger, a blockchain is typically managed by a peer-to-peer network for use as a publicly distributed ledger, where nodes collectively adhere to a protocol to communicate and validate new blocks."""
                    ),
                    "source": "educational",
                    "category": "fundamentals",
                    "url": "https://en.bitcoin.it/wiki/Block_chain",
                    "canonical_urls": [
                        "https://en.bitcoin.it/wiki/Block_chain",
                        "https://bitcoin.org/en/how-it-works",
                        "https://developer.bitcoin.org/devguide/",
                    ],
                },
                {
                    "id": "bitcoin_security",
                    "title": "Bitcoin Security Best Practices",
                    "content": (
                        """Bitcoin security involves protecting private keys and ensuring safe transactions. Key practices include using hardware wallets for cold storage, implementing multi-signature wallets for shared control, and maintaining proper backup procedures. Users should verify transactions before broadcasting, use strong passwords, and keep software updated. Understanding common attack vectors like phishing, malware, and social engineering is crucial for maintaining security."""
                    ),
                    "source": "bitcoin.org",
                    "category": "security",
                    "url": "https://bitcoin.org/en/secure-your-wallet",
                    "canonical_urls": [
                        "https://bitcoin.org/en/secure-your-wallet",
                        "https://en.bitcoin.it/wiki/Securing_your_wallet",
                    ],
                },
                {
                    "id": "bitcoin_mining",
                    "title": "Bitcoin Mining Explained",
                    "content": (
                        """Bitcoin mining is the process of adding transaction records to Bitcoin's public ledger of past transactions. This ledger of past transactions is called the blockchain. Mining involves compiling recent transactions into blocks and trying to solve a computationally difficult puzzle. The participant who first solves the puzzle gets to place the next block on the blockchain and claim the rewards, which include both the transaction fees and newly released bitcoin."""
                    ),
                    "source": "educational",
                    "category": "mining",
                    "url": "https://bitcoin.org/en/how-it-works#mining",
                    "canonical_urls": [
                        "https://bitcoin.org/en/how-it-works#mining",
                        "https://en.bitcoin.it/wiki/Mining",
                    ],
                },
            ]

            # Process resources with URL validation and sanitization
            for resource in resources:
                try:
                    # Validate and sanitize primary URL
                    primary_url = resource.get("url", "")
                    sanitized_url = sanitize_url_for_storage(primary_url)

                    if not sanitized_url:
                        # Try fallback to first canonical URL
                        canonical_urls = resource.get("canonical_urls", [])
                        for fallback_url in canonical_urls:
                            sanitized_url = sanitize_url_for_storage(fallback_url)
                            if sanitized_url:
                                break

                        if not sanitized_url:
                            # Use domain-only fallback
                            sanitized_url = FallbackURLStrategy.domain_only_url(
                                primary_url
                            )
                            self.validation_logger.warning(
                                "Using domain-only fallback URL",
                                extra={
                                    "correlation_id": correlation_id,
                                    "document_id": resource["id"],
                                    "original_url": primary_url,
                                    "fallback_url": sanitized_url,
                                },
                            )

                    # Create document with sanitized URL
                    document = {
                        "id": resource["id"],
                        "title": resource["title"],
                        "content": resource["content"],
                        "source": resource["source"],
                        "category": resource["category"],
                        "url": sanitized_url or "",
                    }

                    # Add canonical URLs if available
                    if "canonical_urls" in resource:
                        validated_canonicals = []
                        for url in resource["canonical_urls"]:
                            sanitized = sanitize_url_for_storage(url)
                            if sanitized:
                                validated_canonicals.append(sanitized)
                        if validated_canonicals:
                            document["canonical_urls"] = validated_canonicals

                    documents.append(document)

                    self.validation_logger.info(
                        "Added document with validated URL",
                        extra={
                            "correlation_id": correlation_id,
                            "document_id": document["id"],
                            "url": document["url"],
                            "category": document["category"],
                            "has_canonical_urls": "canonical_urls" in document,
                        },
                    )

                except Exception as e:
                    self.validation_logger.error(
                        "Failed to process resource",
                        extra={
                            "correlation_id": correlation_id,
                            "resource_id": resource.get("id", "unknown"),
                            "error": str(e),
                        },
                    )
                    # Continue with graceful degradation
                    continue

            self.metrics_logger.info(
                "Bitcoin basics collection completed",
                extra={
                    "correlation_id": correlation_id,
                    "document_count": len(documents),
                    "documents_with_urls": sum(1 for d in documents if d.get("url")),
                },
            )

        return documents

    @exponential_backoff_retry(
        max_retries=3,
        exceptions=(URLValidationError, Exception),
        raise_on_exhaust=False,
    )
    def collect_genius_act_info(self) -> List[Dict[str, Any]]:
        """Collect information about the GENIUS Act with enhanced government URLs"""
        documents = []

        with correlation_context() as correlation_id:
            self.validation_logger.info(
                "Collecting GENIUS Act information",
                extra={"correlation_id": correlation_id},
            )

            # Define legislative resources with official government URLs
            legislative_resources = [
                {
                    "id": "genius_act_overview",
                    "title": "GENIUS Act - Stablecoin Regulation Framework",
                    "content": (
                        """The GENIUS Act (Generating Entrepreneurial Networks to Improve Understanding and Success) S. 1582 from the 119th Congress focuses on establishing a comprehensive regulatory framework for stablecoins and digital assets in the United States. The legislation aims to provide regulatory clarity for stablecoin issuers, establish consumer protections, and create a framework for the oversight of digital payment systems. It addresses key issues including reserve requirements, redemption rights, and supervisory standards for stablecoin providers while fostering innovation in the digital payments ecosystem."""
                    ),
                    "source": "legislative",
                    "category": "regulation",
                    "url": (
                        "https://www.congress.gov/bill/119th-congress/senate-bill/1582"
                    ),
                    "government_urls": [
                        "https://www.congress.gov/bill/119th-congress/senate-bill/1582",
                        "https://www.congress.gov/bill/119th-congress/senate-bill/1582/text",
                        "https://www.congress.gov/bill/119th-congress/senate-bill/1582/actions",
                    ],
                },
                {
                    "id": "genius_act_text",
                    "title": "GENIUS Act - Full Text (Stablecoin Provisions)",
                    "content": (
                        """The full text of S.1582 - GENIUS Act from the 119th Congress establishes comprehensive stablecoin regulations including mandatory reserve requirements, consumer redemption rights, and regulatory oversight mechanisms. The legislation defines stablecoins as digital assets backed by reserves, requires issuers to maintain full backing of outstanding tokens with high-quality liquid assets, and establishes clear supervisory frameworks under federal banking regulators. The act also addresses interoperability standards, consumer disclosures, and enforcement mechanisms for stablecoin compliance."""
                    ),
                    "source": "congress.gov",
                    "category": "regulation",
                    "url": (
                        "https://www.congress.gov/bill/119th-congress/senate-bill/1582/text"
                    ),
                    "government_urls": [
                        "https://www.congress.gov/bill/119th-congress/senate-bill/1582/text",
                        "https://www.govinfo.gov/app/details/BILLS-119s1582is",
                    ],
                },
                {
                    "id": "blockchain_regulatory_framework",
                    "title": "US Blockchain Regulatory Framework",
                    "content": (
                        """The United States blockchain regulatory framework encompasses various federal agencies including the SEC, CFTC, FinCEN, and IRS. Each agency has specific jurisdiction over different aspects of blockchain and cryptocurrency. The SEC oversees securities laws for digital assets, the CFTC regulates cryptocurrency derivatives, FinCEN enforces anti-money laundering rules, and the IRS provides tax guidance for cryptocurrency transactions."""
                    ),
                    "source": "regulatory",
                    "category": "regulation",
                    "url": "https://www.congress.gov/search?q=blockchain+regulation",
                    "government_urls": [
                        "https://www.sec.gov/spotlight/cryptocurrency",
                        "https://www.cftc.gov/digitalassets/index.htm",
                        "https://www.fincen.gov/resources/statutes-and-regulations",
                    ],
                },
            ]

            # Process resources with validation and fallback strategies
            for resource in legislative_resources:
                try:
                    # Validate primary URL
                    primary_url = resource.get("url", "")
                    sanitized_url = sanitize_url_for_storage(primary_url)

                    if not sanitized_url:
                        # Try government URLs as fallback
                        gov_urls = resource.get("government_urls", [])
                        for fallback_url in gov_urls:
                            sanitized_url = sanitize_url_for_storage(fallback_url)
                            if sanitized_url:
                                self.validation_logger.info(
                                    "Using government fallback URL",
                                    extra={
                                        "correlation_id": correlation_id,
                                        "document_id": resource["id"],
                                        "fallback_url": sanitized_url,
                                    },
                                )
                                break

                        if not sanitized_url:
                            # Use domain-only fallback for congress.gov
                            sanitized_url = FallbackURLStrategy.domain_only_url(
                                "https://www.congress.gov"
                            )
                            self.validation_logger.warning(
                                "Using congress.gov domain fallback",
                                extra={
                                    "correlation_id": correlation_id,
                                    "document_id": resource["id"],
                                    "fallback_url": sanitized_url,
                                },
                            )

                    # Create document with validated URL
                    document = {
                        "id": resource["id"],
                        "title": resource["title"],
                        "content": resource["content"],
                        "source": resource["source"],
                        "category": resource["category"],
                        "url": sanitized_url or "",
                    }

                    # Add validated government URLs
                    if "government_urls" in resource:
                        validated_gov_urls = []
                        for gov_url in resource["government_urls"]:
                            sanitized = sanitize_url_for_storage(gov_url)
                            if sanitized:
                                validated_gov_urls.append(sanitized)
                        if validated_gov_urls:
                            document["government_urls"] = validated_gov_urls

                    documents.append(document)

                    self.validation_logger.info(
                        "Added legislative document with URL",
                        extra={
                            "correlation_id": correlation_id,
                            "document_id": document["id"],
                            "url": document["url"],
                            "category": document["category"],
                            "gov_url_count": len(document.get("government_urls", [])),
                        },
                    )

                except Exception as e:
                    self.validation_logger.error(
                        "Failed to process legislative resource",
                        extra={
                            "correlation_id": correlation_id,
                            "resource_id": resource.get("id", "unknown"),
                            "error": str(e),
                        },
                    )
                    # Continue with graceful degradation
                    continue

            self.metrics_logger.info(
                "GENIUS Act collection completed",
                extra={
                    "correlation_id": correlation_id,
                    "document_count": len(documents),
                    "documents_with_urls": sum(1 for d in documents if d.get("url")),
                },
            )

        return documents

    @exponential_backoff_retry(
        max_retries=3,
        exceptions=(URLValidationError, Exception),
        raise_on_exhaust=False,
    )
    def collect_dapp_information(self) -> List[Dict[str, Any]]:
        """Collect dApp information with technical documentation URLs"""
        documents = []

        with correlation_context() as correlation_id:
            self.validation_logger.info(
                "Collecting dApp information", extra={"correlation_id": correlation_id}
            )

            # Define dApp resources with technical documentation
            dapp_resources = [
                {
                    "id": "dapp_basics",
                    "title": "Decentralized Applications (dApps) Overview",
                    "content": (
                        """Decentralized applications (dApps) are digital applications that run on a blockchain or peer-to-peer network of computers instead of a single computer. dApps are outside the purview and control of a single authority. dApps can be developed for a variety of purposes including gaming, finance, and social media. The key characteristics of dApps include: decentralization (no single point of failure), open source code, cryptographic security, and token incentives. Popular dApp categories include DeFi (Decentralized Finance), NFT marketplaces, gaming platforms, and social networks."""
                    ),
                    "source": "educational",
                    "category": "dapps",
                    "url": "https://ethereum.org/en/dapps/",
                    "documentation_urls": [
                        "https://ethereum.org/en/dapps/",
                        "https://ethereum.org/en/developers/docs/dapps/",
                        "https://docs.ethereum.org/en/latest/",
                    ],
                },
                {
                    "id": "dapp_development",
                    "title": "Building Decentralized Applications",
                    "content": (
                        """Developing dApps requires understanding of blockchain technology, smart contracts, and decentralized storage. Common tools include Web3.js for JavaScript integration, Truffle Suite for development framework, Hardhat for Ethereum development, and IPFS for decentralized storage. Developers must consider gas optimization, security audits, and user experience when building dApps."""
                    ),
                    "source": "developer_docs",
                    "category": "dapps",
                    "url": "https://ethereum.org/en/developers/docs/dapps/",
                    "documentation_urls": [
                        "https://web3js.readthedocs.io/en/v1.x/",
                        "https://trufflesuite.com/docs/",
                        "https://hardhat.org/docs",
                        "https://docs.ipfs.tech/",
                    ],
                },
                {
                    "id": "defi_protocols",
                    "title": "DeFi Protocol Architecture",
                    "content": (
                        """Decentralized Finance (DeFi) protocols are smart contract-based applications that recreate traditional financial services without intermediaries. Key components include automated market makers (AMMs), lending protocols, yield aggregators, and decentralized exchanges (DEXs). Popular DeFi protocols include Uniswap, Aave, Compound, and MakerDAO."""
                    ),
                    "source": "technical",
                    "category": "dapps",
                    "url": "https://docs.uniswap.org/",
                    "documentation_urls": [
                        "https://docs.uniswap.org/",
                        "https://docs.aave.com/developers/",
                        "https://docs.compound.finance/",
                        "https://docs.makerdao.com/",
                    ],
                },
                {
                    "id": "smart_contract_security",
                    "title": "Smart Contract Security Best Practices",
                    "content": (
                        """Smart contract security is critical for dApp development. Common vulnerabilities include reentrancy attacks, integer overflow/underflow, and access control issues. Best practices include using established libraries like OpenZeppelin, conducting thorough testing with tools like Mythril and Slither, and getting professional audits before mainnet deployment."""
                    ),
                    "source": "security",
                    "category": "dapps",
                    "url": "https://docs.openzeppelin.com/contracts/",
                    "documentation_urls": [
                        "https://docs.openzeppelin.com/contracts/",
                        "https://consensys.github.io/smart-contract-best-practices/",
                        "https://github.com/crytic/slither#slither-the-solidity-source-analyzer",
                        "https://mythril-classic.readthedocs.io/",
                    ],
                },
                {
                    "id": "blockchain_apis",
                    "title": "Blockchain API Documentation",
                    "content": (
                        """Blockchain APIs provide programmatic access to blockchain data and functionality. Popular providers include Infura for Ethereum node access, Alchemy for enhanced APIs, The Graph for indexing blockchain data, and Moralis for Web3 development. These APIs enable developers to build dApps without running their own nodes."""
                    ),
                    "source": "api_docs",
                    "category": "dapps",
                    "url": "https://docs.infura.io/api",
                    "documentation_urls": [
                        "https://docs.infura.io/api",
                        "https://docs.alchemy.com/",
                        "https://thegraph.com/docs/",
                        "https://docs.moralis.io/",
                    ],
                },
            ]

            # Process resources with validation
            for resource in dapp_resources:
                try:
                    # Validate primary URL
                    primary_url = resource.get("url", "")
                    sanitized_url = sanitize_url_for_storage(primary_url)

                    if not sanitized_url:
                        # Try documentation URLs as fallback
                        doc_urls = resource.get("documentation_urls", [])
                        for fallback_url in doc_urls:
                            sanitized_url = sanitize_url_for_storage(fallback_url)
                            if sanitized_url:
                                self.validation_logger.info(
                                    "Using documentation fallback URL",
                                    extra={
                                        "correlation_id": correlation_id,
                                        "document_id": resource["id"],
                                        "fallback_url": sanitized_url,
                                    },
                                )
                                break

                        if not sanitized_url:
                            # Extract domain as final fallback
                            if doc_urls:
                                domain = extract_domain(doc_urls[0])
                                if domain:
                                    sanitized_url = f"https://{domain}"
                                    self.validation_logger.warning(
                                        "Using domain fallback for dApp",
                                        extra={
                                            "correlation_id": correlation_id,
                                            "document_id": resource["id"],
                                            "fallback_url": sanitized_url,
                                        },
                                    )

                    # Create document
                    document = {
                        "id": resource["id"],
                        "title": resource["title"],
                        "content": resource["content"],
                        "source": resource["source"],
                        "category": resource["category"],
                        "url": sanitized_url or "",
                    }

                    # Add validated documentation URLs
                    if "documentation_urls" in resource:
                        validated_doc_urls = []
                        for doc_url in resource["documentation_urls"]:
                            sanitized = sanitize_url_for_storage(doc_url)
                            if sanitized:
                                validated_doc_urls.append(sanitized)
                        if validated_doc_urls:
                            document["documentation_urls"] = validated_doc_urls

                    documents.append(document)

                    self.validation_logger.info(
                        "Added dApp document with URL",
                        extra={
                            "correlation_id": correlation_id,
                            "document_id": document["id"],
                            "url": document["url"],
                            "category": document["category"],
                            "doc_url_count": len(
                                document.get("documentation_urls", [])
                            ),
                        },
                    )

                except Exception as e:
                    self.validation_logger.error(
                        "Failed to process dApp resource",
                        extra={
                            "correlation_id": correlation_id,
                            "resource_id": resource.get("id", "unknown"),
                            "error": str(e),
                        },
                    )
                    # Continue with graceful degradation
                    continue

            self.metrics_logger.info(
                "dApp collection completed",
                extra={
                    "correlation_id": correlation_id,
                    "document_count": len(documents),
                    "documents_with_urls": sum(1 for d in documents if d.get("url")),
                },
            )

        return documents

    def validate_document_urls(
        self, documents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Validate all URLs in a batch of documents.

        This method validates URLs in batch for performance, logs validation
        results, and returns documents with sanitized URLs. It continues
        operation even if some URLs fail validation.

        Args:
            documents: List of documents to validate

        Returns:
            List of documents with validated and sanitized URLs
        """
        if not documents:
            return documents

        with correlation_context() as correlation_id:
            self.validation_logger.info(
                "Starting batch URL validation",
                extra={
                    "correlation_id": correlation_id,
                    "document_count": len(documents),
                },
            )

            # Collect all unique URLs for batch validation
            all_urls = set()
            url_to_docs: Dict[str, List[Tuple[str, Dict[str, Any]]]] = (
                {}
            )  # Map URLs to documents that contain them

            for doc in documents:
                # Primary URL
                if doc.get("url"):
                    all_urls.add(doc["url"])
                    if doc["url"] not in url_to_docs:
                        url_to_docs[doc["url"]] = []
                    url_to_docs[doc["url"]].append(("primary", doc))

                # Canonical URLs
                for url in doc.get("canonical_urls", []):
                    all_urls.add(url)
                    if url not in url_to_docs:
                        url_to_docs[url] = []
                    url_to_docs[url].append(("canonical", doc))

                # Government URLs
                for url in doc.get("government_urls", []):
                    all_urls.add(url)
                    if url not in url_to_docs:
                        url_to_docs[url] = []
                    url_to_docs[url].append(("government", doc))

                # Documentation URLs
                for url in doc.get("documentation_urls", []):
                    all_urls.add(url)
                    if url not in url_to_docs:
                        url_to_docs[url] = []
                    url_to_docs[url].append(("documentation", doc))

            # Validate URLs in batch
            self.validation_logger.info(
                "Validating URLs in batch",
                extra={"correlation_id": correlation_id, "url_count": len(all_urls)},
            )

            # Use batch validation for efficiency
            validation_results = validate_url_batch(
                list(all_urls),
                check_accessibility=self.check_url_accessibility,
                max_workers=10,
            )

            # Process validation results
            validated_documents = []
            url_validation_stats = {"valid": 0, "invalid": 0, "sanitized": 0}

            for doc in documents:
                validated_doc = doc.copy()

                # Validate and sanitize primary URL
                if doc.get("url"):
                    url = doc["url"]
                    result = validation_results.get(url, {})

                    if result.get("valid") and result.get("normalized"):
                        validated_doc["url"] = result["normalized"]
                        url_validation_stats["valid"] += 1
                    else:
                        # Try fallback strategies
                        fallback_url = FallbackURLStrategy.domain_only_url(url)
                        if fallback_url:
                            validated_doc["url"] = fallback_url
                            url_validation_stats["sanitized"] += 1
                            self.validation_logger.warning(
                                "Used fallback URL for document",
                                extra={
                                    "correlation_id": correlation_id,
                                    "document_id": doc.get("id", "unknown"),
                                    "original_url": url,
                                    "fallback_url": fallback_url,
                                },
                            )
                        else:
                            validated_doc["url"] = ""
                            url_validation_stats["invalid"] += 1

                # Validate URL arrays
                for url_field in [
                    "canonical_urls",
                    "government_urls",
                    "documentation_urls",
                ]:
                    if url_field in doc:
                        validated_urls = []
                        for url in doc[url_field]:
                            result = validation_results.get(url, {})
                            if result.get("valid") and result.get("normalized"):
                                validated_urls.append(result["normalized"])
                                url_validation_stats["valid"] += 1
                            else:
                                url_validation_stats["invalid"] += 1

                        if validated_urls:
                            validated_doc[url_field] = validated_urls
                        else:
                            # Remove field if no valid URLs
                            validated_doc.pop(url_field, None)

                # Apply null-safe metadata
                validated_doc = GracefulDegradation.null_safe_metadata(validated_doc)

                validated_documents.append(validated_doc)

            # Log validation summary
            self.metrics_logger.info(
                "Batch URL validation completed",
                extra={
                    "correlation_id": correlation_id,
                    "document_count": len(validated_documents),
                    "urls_validated": len(all_urls),
                    "valid_urls": url_validation_stats["valid"],
                    "invalid_urls": url_validation_stats["invalid"],
                    "sanitized_urls": url_validation_stats["sanitized"],
                },
            )

            # Record metrics
            for stat_type, count in url_validation_stats.items():
                self.monitor.record_batch_operation(
                    operation_type=f"url_validation_{stat_type}",
                    item_count=count,
                    success=(stat_type != "invalid"),
                    duration_ms=0,  # Not tracking individual durations here
                )

            return validated_documents

    def collect_all_documents(
        self, max_news_articles: int = 30
    ) -> List[Dict[str, Any]]:
        """Collect all documents from various sources"""
        all_documents = []

        with correlation_context() as main_correlation_id:
            self.validation_logger.info(
                "Starting document collection",
                extra={
                    "correlation_id": main_correlation_id,
                    "max_news_articles": max_news_articles,
                },
            )

            collection_start = time.time()

            try:
                print("Collecting Bitcoin basics...")
                bitcoin_docs = self.collect_bitcoin_basics()
                all_documents.extend(bitcoin_docs)
            except Exception as e:
                self.validation_logger.error(
                    "Failed to collect Bitcoin basics",
                    extra={"correlation_id": main_correlation_id, "error": str(e)},
                )

            try:
                print("Collecting GENIUS Act information...")
                genius_docs = self.collect_genius_act_info()
                all_documents.extend(genius_docs)
            except Exception as e:
                self.validation_logger.error(
                    "Failed to collect GENIUS Act info",
                    extra={"correlation_id": main_correlation_id, "error": str(e)},
                )

            try:
                print("Collecting dApp information...")
                dapp_docs = self.collect_dapp_information()
                all_documents.extend(dapp_docs)
            except Exception as e:
                self.validation_logger.error(
                    "Failed to collect dApp information",
                    extra={"correlation_id": main_correlation_id, "error": str(e)},
                )

            try:
                print("Collecting news articles...")
                news_docs = self.collect_from_rss(max_news_articles)
                all_documents.extend(news_docs)
            except Exception as e:
                self.validation_logger.error(
                    "Failed to collect news articles",
                    extra={"correlation_id": main_correlation_id, "error": str(e)},
                )

            # Validate all document URLs in batch
            print("Validating document URLs...")
            all_documents = self.validate_document_urls(all_documents)

            collection_duration = (time.time() - collection_start) * 1000

            # Count URLs in documents
            url_count = sum(1 for doc in all_documents if doc.get("url"))

            self.metrics_logger.info(
                "Document collection completed",
                extra={
                    "correlation_id": main_correlation_id,
                    "total_documents": len(all_documents),
                    "documents_with_urls": url_count,
                    "duration_ms": collection_duration,
                },
            )

            print(f"Total documents collected: {len(all_documents)}")
            return all_documents

    @exponential_backoff_retry(
        max_retries=2, exceptions=(IOError, OSError), raise_on_exhaust=True
    )
    def save_documents(
        self, documents: List[Dict[str, Any]], filename: str = "bitcoin_documents.json"
    ):
        """Save documents to JSON file with error handling

        Args:
            documents: List of documents to save
            filename: Name of the file to save to in the data directory

        Raises:
            IOError: If there are I/O errors after retries
            OSError: If there are OS-level errors after retries
        """
        # Ensure data directory exists
        os.makedirs("data", exist_ok=True)

        # Apply graceful degradation to all documents
        safe_documents = [
            GracefulDegradation.null_safe_metadata(doc) for doc in documents
        ]

        filepath = f"data/{filename}"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(safe_documents, f, indent=2, ensure_ascii=False)
        print(f"Documents saved to {filepath}")

        self.validation_logger.info(
            "Documents saved successfully",
            extra={
                "filename": filename,
                "document_count": len(documents),
                "filepath": filepath,
            },
        )

    @exponential_backoff_retry(
        max_retries=2,
        exceptions=(IOError, OSError, json.JSONDecodeError),
        raise_on_exhaust=True,
    )
    def load_documents(
        self, filename: str = "bitcoin_documents.json"
    ) -> List[Dict[str, Any]]:
        """Load documents from JSON file with retry logic for transient I/O errors.

        Args:
            filename: Name of the file to load from the data directory

        Returns:
            List of loaded documents

        Raises:
            FileNotFoundError: If the file doesn't exist
            json.JSONDecodeError: If the file contains invalid JSON
            IOError: If there are I/O errors after retries
            OSError: If there are OS-level errors after retries
        """
        filepath = f"data/{filename}"
        with open(filepath, "r", encoding="utf-8") as f:
            documents = json.load(f)

        self.validation_logger.info(
            "Documents loaded successfully",
            extra={
                "filename": filename,
                "document_count": len(documents),
                "filepath": filepath,
            },
        )

        return documents
